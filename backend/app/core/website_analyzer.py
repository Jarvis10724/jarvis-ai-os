"""
Lightweight website crawler/analyzer for the Build a Website "Improve Existing
Website" mode. Fetches a page (and optionally a couple of internal links) and
extracts branding + structure signals to feed the improvement plan:

- brand name (og:site_name / <title>)
- description (meta description / og:description)
- palette hints (hex colors found in inline styles / <meta theme-color>)
- fonts (font-family hints)
- headings (h1/h2) as existing messaging
- internal nav links -> existing sitemap
- logo image URL guess

Uses only httpx + the stdlib HTML parser (no extra deps). SSRF-guarded: refuses
non-http(s) schemes and private/loopback hosts.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from app.exceptions import ValidationError
from app.logging_config import get_logger

logger = get_logger(__name__)

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
_FONT_RE = re.compile(r"font-family\s*:\s*([^;\"'}]+)", re.IGNORECASE)


def _is_public_host(host: str) -> bool:
    """Block loopback/private/link-local/reserved targets to prevent SSRF."""
    if not host:
        return False
    if host.lower() in ("localhost", "localhost.localdomain"):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            return False
    return True


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValidationError("A website URL is required.")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValidationError("Only http(s) URLs can be analyzed.")
    if not _is_public_host(parsed.hostname or ""):
        raise ValidationError("That host can't be analyzed (private/loopback addresses are blocked).")
    return url


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta: dict[str, str] = {}
        self.headings: list[str] = []
        self.links: list[str] = []
        self.styles: list[str] = []
        self.logo: str | None = None
        self._cur: str | None = None
        self._capture_text = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content"):
                self.meta[key] = a["content"]
        elif tag in ("h1", "h2", "title"):
            self._cur = tag
            self._capture_text = True
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "img":
            src = a.get("src") or ""
            alt = (a.get("alt") or "").lower()
            cls = (a.get("class") or "").lower()
            if self.logo is None and ("logo" in alt or "logo" in cls or "logo" in src.lower()):
                self.logo = src
        elif a.get("style"):
            self.styles.append(a["style"])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "title"):
            self._capture_text = False
            self._cur = None

    def handle_data(self, data):
        if not (self._capture_text and data.strip()):
            return
        text = " ".join(data.split())[:200]
        if self._cur == "title":
            if not self.title:
                self.title = text
        else:
            self.headings.append(text[:160])


async def analyze(url: str, *, max_pages: int = 3) -> dict:
    """Crawl the URL (+ up to a couple internal links) and return a branding/
    structure summary. Raises ValidationError on bad/blocked URLs; on fetch
    failure returns a minimal record so the build can proceed."""
    start = _normalize_url(url)
    origin = urlparse(start)
    base = f"{origin.scheme}://{origin.netloc}"

    pages: list[dict] = []
    palette: list[str] = []
    fonts: list[str] = []
    nav: list[str] = []
    brand = ""
    description = ""
    logo = None

    to_fetch = [start]
    fetched: set[str] = set()
    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True, headers={"User-Agent": "JarvisWebsiteBuilder/1.0"}
        ) as client:
            while to_fetch and len(fetched) < max_pages:
                current = to_fetch.pop(0)
                if current in fetched:
                    continue
                fetched.add(current)
                try:
                    resp = await client.get(current)
                    if "text/html" not in resp.headers.get("content-type", ""):
                        continue
                    html = resp.text[:400_000]
                except httpx.HTTPError as exc:
                    logger.warning("analyze_fetch_failed", url=current, error=str(exc))
                    continue

                ex = _Extractor()
                try:
                    ex.feed(html)
                except Exception:  # noqa: BLE001 - never let a parse error abort analysis
                    pass

                if not brand:
                    brand = ex.meta.get("og:site_name") or ex.title or origin.netloc
                if not description:
                    description = ex.meta.get("description") or ex.meta.get("og:description") or ""
                if logo is None and ex.logo:
                    logo = urljoin(current, ex.logo)

                # palette from inline styles + theme-color
                for style in ex.styles:
                    palette.extend(_HEX_RE.findall(style))
                    fonts.extend(f.strip() for f in _FONT_RE.findall(style))
                if ex.meta.get("theme-color"):
                    palette.extend(_HEX_RE.findall(ex.meta["theme-color"]))

                # internal nav / next pages
                for href in ex.links:
                    absu = urljoin(current, href)
                    p = urlparse(absu)
                    if p.netloc == origin.netloc and p.scheme in ("http", "https"):
                        path = p.path or "/"
                        if path not in nav:
                            nav.append(path)
                        clean = f"{base}{path}"
                        if clean not in fetched and clean not in to_fetch and len(nav) <= 12:
                            to_fetch.append(clean)

                pages.append(
                    {"url": current, "title": ex.title, "headings": ex.headings[:8]}
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("analyze_failed", url=start, error=str(exc))

    # de-dupe, keep order
    def _uniq(seq):
        seen, out = set(), []
        for x in seq:
            k = x.lower()
            if k not in seen:
                seen.add(k)
                out.append(x)
        return out

    return {
        "source_url": start,
        "brand": brand,
        "description": description,
        "logo": logo,
        "palette": _uniq(palette)[:8],
        "fonts": _uniq(fonts)[:4],
        "nav": nav[:12],
        "pages": pages,
        "fetched": len(fetched),
    }

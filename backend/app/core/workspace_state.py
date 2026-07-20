"""
Structured-state plumbing for Quick-Action workspaces.

Turns the ``jarvis-state`` block a studio model emits into merged
`WorkspaceSession.state_json`, and standardizes the richer artifact records
(with kind/version) that power version history and export panels. Kept
separate from the endpoint so it's unit-testable without HTTP.
"""
from __future__ import annotations

import json
import re
import time
import uuid

# Matches a single ```jarvis-state ... ``` fenced block (case-insensitive
# label, tolerant of surrounding whitespace). DOTALL so it spans lines.
_STATE_BLOCK = re.compile(r"```[ \t]*jarvis-state[ \t]*\r?\n(.*?)```", re.IGNORECASE | re.DOTALL)
# Any fenced block (```lang\n...```), used to catch a state block the model
# mislabeled as ```json / ``` instead of ```jarvis-state.
_ANY_FENCE = re.compile(r"```[ \t]*[A-Za-z0-9_-]*[ \t]*\r?\n(.*?)```", re.DOTALL)


def _find_mislabeled_state(text: str, known_keys) -> tuple[int, int, dict] | None:
    """Find a fenced block the model used for structured state but labelled
    wrong (```json or bare ```). Precise: only a block whose parsed JSON object
    actually shares a key with this action's state schema counts — code blocks
    and unrelated JSON never match. Returns (start, end, patch) for the LAST
    such block, or None."""
    keyset = set(known_keys or ())
    if not keyset:
        return None
    hit = None
    for m in _ANY_FENCE.finditer(text):
        obj = _try_json(m.group(1).strip())
        if isinstance(obj, dict) and keyset & set(obj):
            hit = (m.start(), m.end(), obj)  # keep last
    return hit


def _try_json(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def extract_state_block(text: str, known_keys=None) -> tuple[str, dict | None]:
    """Pull the ``jarvis-state`` JSON out of a streamed reply.

    Returns ``(visible_text, state_patch)`` where ``visible_text`` is the reply
    with the block removed (so the chat column stays clean prose) and
    ``state_patch`` is the parsed object, or ``None`` if there was no valid
    block. Never raises on bad JSON — a malformed block is just left in place
    and ignored, so a model slip degrades to plain chat rather than an error.
    """
    match = _STATE_BLOCK.search(text)
    if match:
        raw = match.group(1).strip()
        visible = (text[: match.start()] + text[match.end() :]).strip()
        try:
            patch = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            patch = None
        return visible, (patch if isinstance(patch, dict) else None)

    # The model may have put the state in a mislabeled fence (```json / ```).
    # Detect it precisely via the action's known state keys and strip it so the
    # chat transcript never shows raw JSON.
    mislabeled = _find_mislabeled_state(text, known_keys)
    if mislabeled:
        start, end, patch = mislabeled
        visible = (text[:start] + text[end:]).strip()
        return visible, patch

    # No *closed* block. If the model still opened a `jarvis-state` fence but
    # ran out of tokens before closing it, strip from the opener to the end so
    # the chat never shows raw JSON — and best-effort parse the remainder (a
    # truncated object won't parse, so we degrade to "no merge" cleanly).
    opener = _FENCE_START.search(text)
    if not opener:
        return text, None
    visible = text[: opener.start()].strip()
    tail = text[opener.end() :].lstrip()
    if tail.startswith("\n"):
        tail = tail[1:]
    tail = tail.rstrip("` \n\r\t")
    try:
        patch = json.loads(tail)
    except (json.JSONDecodeError, ValueError):
        patch = None
    return visible, (patch if isinstance(patch, dict) else None)


_FENCE_START = re.compile(r"```[ \t]*jarvis-state", re.IGNORECASE)
# Longest possible partial fence marker we must hold back while streaming so a
# marker split across chunks is never emitted then retracted. "``` jarvis-state".
_FENCE_GUARD = 18


class VisibleStreamer:
    """Streams a reply's prose while suppressing its trailing ``jarvis-state``
    block token-by-token, so the live chat never flashes raw JSON. Feed each
    chunk; it returns only the text safe to show, holding back a small tail
    that could be the start of the fence. Call ``flush`` at the end."""

    def __init__(self) -> None:
        self._buf = ""
        self._done = False  # hit the fence — everything after is state, drop it

    def feed(self, chunk: str) -> str:
        if self._done:
            return ""
        self._buf += chunk
        match = _FENCE_START.search(self._buf)
        if match:
            out = self._buf[: match.start()]
            self._buf = ""
            self._done = True
            return out
        if len(self._buf) > _FENCE_GUARD:
            out = self._buf[:-_FENCE_GUARD]
            self._buf = self._buf[-_FENCE_GUARD:]
            return out
        return ""

    def flush(self) -> str:
        out = self._buf
        self._buf = ""
        return out


def parse_loose_json(text: str) -> dict | None:
    """Best-effort parse of a model reply that should be a JSON object but may
    be wrapped in a code fence, prefixed with ``json``, or padded with prose.
    Returns the dict or None — never raises. Used by the structuring fallback
    (see workspaces._structure_state)."""
    if not text:
        return None
    t = text.strip()
    # Strip a leading ``` / ```json fence and its closing fence.
    if t.startswith("```"):
        t = t[3:]
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.rsplit("```", 1)[0].strip()
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    # Fall back to the outermost {...} span.
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(t[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def deep_merge(base: dict, patch: dict) -> dict:
    """Merge ``patch`` into ``base`` (returns a new dict).

    Nested objects are merged recursively; every other value — including lists —
    is replaced. That matches the contract we give the model: "only emit the
    keys you change; for a list, emit its full new value." Predictable and
    lossless for unchanged keys.
    """
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_json(raw: str | None, default):
    try:
        return json.loads(raw) if raw else default
    except (json.JSONDecodeError, ValueError):
        return default


def make_artifact(
    *, title: str, content: str, kind: str = "document", stage: str = "", version: int = 1
) -> dict:
    """A standardized artifact record. Older rows may only have {title, content};
    readers must tolerate missing keys."""
    return {
        "id": uuid.uuid4().hex,
        "kind": kind,
        "title": title[:200],
        "content": content,
        "stage": stage,
        "version": version,
        "ts": time.time(),
    }


def next_version(artifacts: list[dict], title: str) -> int:
    """Version number for a new artifact sharing a title (the version-history
    chain). Lenient about legacy records without a version field."""
    prior = [a for a in artifacts if a.get("title") == title[:200]]
    if not prior:
        return 1
    return max(int(a.get("version", 1)) for a in prior) + 1

import { Fragment } from "react";

// A deliberately small markdown renderer — enough to make workspace
// deliverables (headings, bullet/numbered lists, bold, fenced code) read like
// a document rather than a raw chat blob, without pulling in a full markdown
// dependency. Not CommonMark-complete; covers what the studios actually emit.

function renderInline(text: string, keyBase: string) {
  // Bold (**x**) and inline `code`.
  const parts: (string | JSX.Element)[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      parts.push(
        <strong key={`${keyBase}-b-${i++}`} className="font-semibold text-jarvis-text">
          {tok.slice(2, -2)}
        </strong>
      );
    } else {
      parts.push(
        <code key={`${keyBase}-c-${i++}`} className="rounded bg-jarvis-panel3/70 px-1 py-0.5 font-data text-[0.85em] text-jarvis-cyan">
          {tok.slice(1, -1)}
        </code>
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export default function MarkdownLite({ content }: { content: string }) {
  const lines = content.split("\n");
  const blocks: JSX.Element[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.trim().startsWith("```")) {
      const lang = line.trim().slice(3).trim();
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i++;
      }
      i++; // closing fence
      blocks.push(
        <pre
          key={key++}
          className="my-2 overflow-x-auto rounded-xl border border-jarvis-border/70 bg-jarvis-panel3/50 p-3 font-data text-xs leading-relaxed text-jarvis-text"
        >
          {lang && <div className="mb-1 text-[10px] uppercase tracking-wide text-jarvis-faint">{lang}</div>}
          <code>{code.join("\n")}</code>
        </pre>
      );
      continue;
    }

    // Headings
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      const level = h[1].length;
      const sizes = ["text-base", "text-sm", "text-sm", "text-xs"];
      blocks.push(
        <div
          key={key++}
          className={`mt-3 mb-1 font-display font-bold tracking-wide text-jarvis-text ${sizes[level - 1]}`}
        >
          {renderInline(h[2], `h${key}`)}
        </div>
      );
      i++;
      continue;
    }

    // List (bullet or numbered) — collect consecutive items
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
        i++;
      }
      blocks.push(
        <ul key={key++} className="my-1.5 space-y-1 pl-1">
          {items.map((it, idx) => (
            <li key={idx} className="flex gap-2 text-sm leading-relaxed text-jarvis-text">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-jarvis-cyan" />
              <span>{renderInline(it, `li${key}-${idx}`)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // Blank line → spacer
    if (!line.trim()) {
      i++;
      continue;
    }

    // Paragraph
    blocks.push(
      <p key={key++} className="my-1.5 text-sm leading-relaxed text-jarvis-text">
        {renderInline(line, `p${key}`)}
      </p>
    );
    i++;
  }

  return <Fragment>{blocks}</Fragment>;
}

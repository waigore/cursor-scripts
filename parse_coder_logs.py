#!/usr/bin/env python3
"""
Parse Cursor agent JSONL logs and emit Markdown: session summary then chronological transcript.
Usage: python parse_coder_logs.py [input.jsonl] [-o output.md] [--truncate N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_TRUNCATE_LINES = 20
TOOL_KIND_MAP = {
    "readToolCall": "read",
    "shellToolCall": "shell",
    "grepToolCall": "grep",
    "editToolCall": "edit",
    "globToolCall": "glob",
    "updateTodosToolCall": "todos",
}


def load_records(path: str | Path) -> list[dict]:
    """Read JSONL file and return list of record dicts in order."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def get_result_record(records: list[dict]) -> dict | None:
    """Return the last record with type=='result' and subtype=='success', or None."""
    for i in range(len(records) - 1, -1, -1):
        r = records[i]
        if r.get("type") == "result" and r.get("subtype") == "success":
            return r
    return None


def format_duration(ms: int | None) -> str:
    """Format milliseconds as human-readable (e.g. '5m 2s')."""
    if ms is None or ms < 0:
        return "—"
    sec = ms / 1000
    if sec < 60:
        return f"{sec:.1f}s"
    m = int(sec // 60)
    s = int(sec % 60)
    if m >= 60:
        h = m // 60
        m = m % 60
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


def format_summary(result_record: dict | None) -> str:
    """Build Markdown summary section from result record (or placeholder)."""
    lines = ["# Session transcript", "", "## Summary", ""]
    if result_record is None:
        lines.append("- **Duration:** —")
        lines.append("- **Status:** No session result record.")
        lines.append("")
        return "\n".join(lines)

    duration_ms = result_record.get("duration_ms")
    is_error = result_record.get("is_error", False)
    lines.append(f"- **Duration:** {format_duration(duration_ms)}")
    lines.append(f"- **Status:** {'Error' if is_error else 'Success'}")
    lines.append("")
    result_text = result_record.get("result") or ""
    if result_text.strip():
        lines.append(result_text.strip())
        lines.append("")
    return "\n".join(lines)


def _extract_tool_call_info(tool_call: dict) -> tuple[str, str]:
    """From tool_call payload get (kind, descriptor). kind is e.g. 'read', descriptor for header."""
    for key, value in tool_call.items():
        if key in ("args", "result"):
            continue
        kind = TOOL_KIND_MAP.get(key, key.replace("ToolCall", "").lower() if key.endswith("ToolCall") else key)
        if not isinstance(value, dict):
            return kind, ""
        args = value.get("args") or {}
        if "path" in args:
            return kind, str(args["path"])
        if "command" in args:
            cmd = args["command"]
            return kind, cmd[:80] + ("..." if len(cmd) > 80 else "")
        if "pattern" in args:
            return kind, repr(args["pattern"])[:60]
        if "globPattern" in args:
            return kind, str(args["globPattern"])[:60]
        return kind, ""
    return "tool", ""


def _tool_result_content_to_str(content: str | list) -> str:
    """Normalize tool result content to a single string (handles MCP list format)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content) if content else ""
    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
        elif isinstance(text, dict) and "text" in text:
            parts.append(str(text.get("text", "")))
    return "\n".join(parts)


def _truncate_text(text: str, max_lines: int) -> str:
    """Return text truncated to max_lines with a trailing note if truncated."""
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + "\n\n(truncated)"


def _format_tool_result(tool_call: dict, truncate_lines: int) -> str:
    """Format the result part of a completed tool_call for Markdown."""
    for key, value in (tool_call or {}).items():
        if key in ("args", "result") or not isinstance(value, dict):
            continue
        result = value.get("result")
        if not isinstance(result, dict):
            continue
        success = result.get("success")
        if success is None:
            continue
        if "content" in success:
            content = _tool_result_content_to_str(success.get("content") or "")
            return _truncate_text(content, truncate_lines)
        if "stdout" in success or "stderr" in success:
            out = (success.get("stdout") or "") + (success.get("stderr") or "")
            exit_code = success.get("exitCode", "?")
            return f"Exit: {exit_code}\n\n" + _truncate_text(out, truncate_lines)
        if "workspaceResults" in success or "matches" in str(success):
            # grep-style: summarize
            try:
                wr = success.get("workspaceResults", {})
                total = 0
                for w in wr.values():
                    c = w.get("content", {}) if isinstance(w, dict) else {}
                    m = c.get("matches", [])
                    total += len(m) if isinstance(m, list) else 0
                return f"Matches: {total} (truncated listing omitted)"
            except Exception:
                return _truncate_text(json.dumps(success)[:1024], truncate_lines)
        if "todos" in success:
            return "(todos updated)"
    return ""


def format_transcript(
    records: list[dict],
    result_record: dict | None,
    truncate_lines: int = DEFAULT_TRUNCATE_LINES,
) -> str:
    """Build chronological transcript in Markdown. Skips result records (used in summary)."""
    out = []
    thinking_buf: list[str] = []

    def flush_thinking() -> None:
        nonlocal thinking_buf
        if thinking_buf:
            text = "".join(thinking_buf).strip()
            if text:
                out.append("### Thinking")
                out.append("")
                out.append(_truncate_text(text, truncate_lines * 2))
                out.append("")
            thinking_buf.clear()

    for r in records:
        typ = r.get("type") or ""
        subtype = r.get("subtype") or ""

        if typ == "result":
            continue

        if typ == "system" and subtype == "init":
            flush_thinking()
            cwd = r.get("cwd", "")
            model = r.get("model", "")
            out.append("### Session")
            out.append("")
            out.append(f"- **CWD:** {cwd}")
            out.append(f"- **Model:** {model}")
            out.append("")
            continue

        if typ == "user":
            flush_thinking()
            msg = r.get("message") or {}
            content = msg.get("content") or []
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            text = "".join(texts).strip()
            out.append("### User")
            out.append("")
            if text:
                out.append(text)
            out.append("")
            continue

        if typ == "thinking":
            if subtype == "delta":
                thinking_buf.append(r.get("text") or "")
            else:
                flush_thinking()
            continue

        if typ == "assistant":
            flush_thinking()
            msg = r.get("message") or {}
            content = msg.get("content") or []
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            text = "".join(texts).strip()
            out.append("### Assistant")
            out.append("")
            if text:
                out.append(text)
            out.append("")
            continue

        if typ == "tool_call":
            flush_thinking()
            tc = r.get("tool_call") or {}
            kind, descriptor = _extract_tool_call_info(tc)
            if subtype == "started":
                title = f"### Tool: {kind}"
                if descriptor:
                    title += f" — {descriptor}"
                out.append(title)
                out.append("")
            elif subtype == "completed":
                result_block = _format_tool_result(tc, truncate_lines)
                if result_block:
                    out.append("```")
                    out.append(result_block)
                    out.append("```")
                    out.append("")
            continue

    flush_thinking()
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse Cursor agent JSONL logs and output Markdown (summary + transcript)."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="cursor_coder.jsonl",
        help="Input JSONL file (default: cursor_coder.jsonl)",
    )
    parser.add_argument(
        "-o", "--output",
        type=argparse.FileType("w", encoding="utf-8"),
        default=None,
        help="Output file (default: stdout)",
    )
    parser.add_argument(
        "--truncate",
        type=int,
        default=DEFAULT_TRUNCATE_LINES,
        metavar="N",
        help=f"Truncate tool output to N lines (default: {DEFAULT_TRUNCATE_LINES})",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    records = load_records(input_path)
    result_record = get_result_record(records)

    summary = format_summary(result_record)
    transcript = format_transcript(records, result_record, truncate_lines=args.truncate)

    md = summary + "\n---\n\n## Transcript\n\n" + transcript + "\n"

    out = args.output or sys.stdout
    out.write(md)
    if args.output:
        args.output.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

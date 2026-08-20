#!/usr/bin/env python3
"""
Format Skeleton Extractor / Restorer.
Preserves Markdown/HTML structure while translating content.

Usage:
    # Extract skeleton
    python format_skeleton.py extract input.md --output skeleton.json

    # Restore skeleton with translated content
    python format_skeleton.py restore skeleton.json translated.txt --output result.md

Skeleton format:
    {
        "blocks": [
            {"type": "heading", "level": 2, "content": "original text"},
            {"type": "paragraph", "content": "original text"},
            {"type": "blockquote", "content": "original text"},
            {"type": "list_item", "content": "original text"},
            {"type": "table_row", "cells": ["cell1", "cell2"]},
            {"type": "raw", "content": "unchanged text"}
        ]
    }
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from _shared import json_output

# --output defaults anchor to the script directory, not the caller's cwd, so
# running from elsewhere never drops skeleton.json/result.md into a random folder.
_DEFAULT_DIR = Path(__file__).resolve().parent


def extract_skeleton(text: str) -> dict:
    """Extract format skeleton from Markdown text."""
    blocks = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Heading
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            content = stripped.lstrip("#").strip()
            blocks.append({
                "type": "heading",
                "level": level,
                "content": content
            })
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            content_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                content_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append({
                "type": "blockquote",
                "content": " ".join(content_lines)
            })
            continue

        # Table
        if "|" in stripped and stripped.startswith("|"):
            rows = []
            separators = []
            while i < len(lines) and "|" in lines[i]:
                row = lines[i].strip()
                if "---" in row:
                    separators.append(row)
                    i += 1
                    continue
                cells = [c.strip() for c in row.split("|")]
                # split("|") 的首尾管道会各产生一个空串，只剥首尾即可；
                # 原写法 [c for c in cells if c] 会把合法的空单元格一并删除，导致列错位。
                if cells and not cells[0]:
                    cells = cells[1:]
                if cells and not cells[-1]:
                    cells = cells[:-1]
                if cells:
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append({
                    "type": "table",
                    "rows": rows,
                    "separator": separators[0] if separators else None
                })
            continue

        # List item
        if re.match(r'^[\s]*[-*+][\s]', stripped):
            content = re.sub(r'^[\s]*[-*+][\s]', '', line)
            blocks.append({
                "type": "list_item",
                "content": content,
                "indent": len(line) - len(line.lstrip())
            })
            i += 1
            continue

        # Numbered list
        if re.match(r'^[\s]*\d+\.[\s]', stripped):
            content = re.sub(r'^[\s]*\d+\.[\s]', '', line)
            number_match = re.match(r'^[\s]*(\d+)\.', stripped)
            number = int(number_match.group(1)) if number_match else 1
            blocks.append({
                "type": "numbered_item",
                "content": content,
                "indent": len(line) - len(line.lstrip()),
                "number": number
            })
            i += 1
            continue

        # Empty line
        if not stripped:
            blocks.append({"type": "empty"})
            i += 1
            continue

        # Paragraph (accumulate consecutive non-special lines)
        para_lines = []
        while i < len(lines):
            l = lines[i]
            s = l.strip()
            if not s or s.startswith("#") or s.startswith(">") or \
               s.startswith("|") or re.match(r'^[\s]*[-*+][\s]', s) or \
               re.match(r'^[\s]*\d+\.[\s]', s):
                break
            para_lines.append(l)
            i += 1

        if para_lines:
            blocks.append({
                "type": "paragraph",
                "content": "\n".join(para_lines)
            })
        else:
            # This line was skipped by paragraph scanner but not handled above.
            # Skip it to avoid infinite loop.
            i += 1
        continue

    return {"blocks": blocks}


def restore_skeleton(skeleton: dict, translated_blocks: list[str]) -> tuple[str, int]:
    """Restore Markdown from skeleton with translated content.

    Returns (markdown, fallback_count). fallback_count counts blocks where the
    UNTRANSLATED original text had to be substituted — translated chunks ran
    out, or a table row's cell count did not match the skeleton. Any non-zero
    count means the output silently contains source-language text; callers
    must treat that as a failure, not ship the result.
    """
    lines = []
    t_idx = 0
    fallbacks = 0

    def next_chunk() -> str | None:
        """Return the next translated chunk, or None if exhausted."""
        nonlocal t_idx
        if t_idx >= len(translated_blocks):
            return None
        chunk = translated_blocks[t_idx]
        t_idx += 1
        return chunk

    for block in skeleton["blocks"]:
        btype = block["type"]

        if btype == "empty":
            lines.append("")
            continue

        if btype == "table":
            # Tables consume one chunk per row; each chunk contains cells joined by ' ||| '.
            for idx, original_row in enumerate(block["rows"]):
                row_text = next_chunk()
                if row_text is None:
                    cells = original_row
                    fallbacks += 1
                else:
                    cells = [c.strip() for c in row_text.split(" ||| ")]
                    # If the translator produced the wrong number of cells, fall back to original.
                    if len(cells) != len(original_row):
                        cells = original_row
                        fallbacks += 1
                lines.append("| " + " | ".join(cells) + " |")
                if idx == 0:
                    sep = block.get("separator")
                    if sep:
                        lines.append(sep)
            continue

        content = next_chunk()
        if content is None:
            content = block.get("content", "")
            fallbacks += 1

        if btype == "heading":
            prefix = "#" * block["level"]
            lines.append(f"{prefix} {content}")

        elif btype == "paragraph":
            lines.append(content)

        elif btype == "blockquote":
            for cl in content.split("\n"):
                lines.append(f"> {cl}")

        elif btype == "list_item":
            indent = " " * block.get("indent", 0)
            lines.append(f"{indent}- {content}")

        elif btype == "numbered_item":
            indent = " " * block.get("indent", 0)
            number = block.get("number", 1)
            lines.append(f"{indent}{number}. {content}")

        elif btype == "raw":
            lines.append(content)

    return "\n".join(lines), fallbacks


def split_into_chunks(skeleton: dict) -> list[str]:
    """Extract just the text content for translation.

    Table rows are emitted as single chunks with cells joined by ' ||| '
    so that restore_skeleton can reconstruct the table structure.
    """
    chunks = []
    for block in skeleton["blocks"]:
        if block["type"] in ("heading", "paragraph", "blockquote", "list_item", "numbered_item"):
            chunks.append(block["content"])
        elif block["type"] == "table":
            for row in block["rows"]:
                chunks.append(" ||| ".join(row))
        elif block["type"] == "raw":
            chunks.append(block["content"])
    return chunks


def main():
    parser = argparse.ArgumentParser(description="Format Skeleton Extractor / Restorer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="Extract skeleton from Markdown")
    extract.add_argument("input", help="Input Markdown file")
    extract.add_argument("--output", default=str(_DEFAULT_DIR / "skeleton.json"), help="Output skeleton file")
    extract.add_argument("--json", action="store_true", help="Output structured JSON")

    restore = subparsers.add_parser("restore", help="Restore Markdown from skeleton")
    restore.add_argument("skeleton", help="Skeleton JSON file")
    restore.add_argument("translated", help="Translated chunks file")
    restore.add_argument("--output", default=str(_DEFAULT_DIR / "result.md"), help="Output Markdown file")
    restore.add_argument("--json", action="store_true", help="Output structured JSON")

    args = parser.parse_args()

    if args.command == "extract":
        input_path = Path(args.input)
        if not input_path.exists():
            if args.json:
                json_output(None, errors=[f"input file not found: {args.input}"], exit_code=1)
            print(f"Error: input file not found: {args.input}")
            sys.exit(1)
        text = input_path.read_text(encoding="utf-8")
        skeleton = extract_skeleton(text)
        Path(args.output).write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
        chunk_count = len(split_into_chunks(skeleton))
        if args.json:
            json_output({
                "command": "extract",
                "input": str(args.input),
                "output": str(args.output),
                "block_count": len(skeleton["blocks"]),
                "chunk_count": chunk_count,
            }, exit_code=0)
        print(f"Extracted {len(skeleton['blocks'])} blocks ({chunk_count} chunks) to {args.output}")

    elif args.command == "restore":
        skeleton_path = Path(args.skeleton)
        translated_path = Path(args.translated)
        if not skeleton_path.exists():
            if args.json:
                json_output(None, errors=[f"skeleton file not found: {args.skeleton}"], exit_code=1)
            print(f"Error: skeleton file not found: {args.skeleton}")
            sys.exit(1)
        if not translated_path.exists():
            if args.json:
                json_output(None, errors=[f"translated file not found: {args.translated}"], exit_code=1)
            print(f"Error: translated file not found: {args.translated}")
            sys.exit(1)
        skeleton = json.loads(skeleton_path.read_text(encoding="utf-8"))
        translated_lines = translated_path.read_text(encoding="utf-8").strip().split("\n---CHUNK---\n")
        result, fallbacks = restore_skeleton(skeleton, translated_lines)
        Path(args.output).write_text(result, encoding="utf-8")
        if fallbacks > 0:
            # The output silently contains UNTRANSLATED original text — the
            # most dangerous failure shape for a translation tool. Fail loudly.
            print(f"[WARN] restore fell back to UNTRANSLATED original text for "
                  f"{fallbacks} block(s) — output is INCOMPLETE, do not ship it.",
                  file=sys.stderr)
        if args.json:
            json_output({
                "command": "restore",
                "skeleton": str(args.skeleton),
                "translated": str(args.translated),
                "output": str(args.output),
                "block_count": len(skeleton["blocks"]),
                "fallback_count": fallbacks,
            }, exit_code=1 if fallbacks > 0 else 0)
        print(f"Restored to {args.output}")
        if fallbacks > 0:
            print(f"[WARN] {fallbacks} block(s) fell back to untranslated original "
                  f"text (see stderr) — output is INCOMPLETE.")
            sys.exit(1)


if __name__ == "__main__":
    main()

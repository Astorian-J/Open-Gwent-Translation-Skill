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

import json
import re
import sys
from pathlib import Path
from typing import Any


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
                cells = [c for c in cells if c]  # Remove empty
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
               s.startswith("|") or re.match(r'^[\s]*[-*+\d]', s):
                break
            para_lines.append(l)
            i += 1

        if para_lines:
            blocks.append({
                "type": "paragraph",
                "content": "\n".join(para_lines)
            })
        continue

    return {"blocks": blocks}


def restore_skeleton(skeleton: dict, translated_blocks: list[str]) -> str:
    """Restore Markdown from skeleton with translated content."""
    lines = []
    t_idx = 0

    for block in skeleton["blocks"]:
        if block["type"] == "empty":
            lines.append("")
            continue

        if t_idx >= len(translated_blocks):
            # No more translated content, keep original
            content = block.get("content", "")
        else:
            content = translated_blocks[t_idx]
            t_idx += 1

        if block["type"] == "heading":
            prefix = "#" * block["level"]
            lines.append(f"{prefix} {content}")

        elif block["type"] == "paragraph":
            lines.append(content)

        elif block["type"] == "blockquote":
            for cl in content.split("\n"):
                lines.append(f"> {cl}")

        elif block["type"] == "list_item":
            indent = " " * block.get("indent", 0)
            lines.append(f"{indent}- {content}")

        elif block["type"] == "numbered_item":
            indent = " " * block.get("indent", 0)
            number = block.get("number", 1)
            lines.append(f"{indent}{number}. {content}")

        elif block["type"] == "table":
            # For tables, content should be a list of cell translations
            if isinstance(content, list):
                for idx, row in enumerate(content):
                    if isinstance(row, list):
                        lines.append("| " + " | ".join(row) + " |")
                    else:
                        lines.append(str(row))
                    # Insert separator after first row if available
                    if idx == 0:
                        sep = block.get("separator")
                        if sep:
                            lines.append(sep)
            else:
                # Fallback: just append as-is
                lines.append(str(content))

        elif block["type"] == "raw":
            lines.append(content)

    return "\n".join(lines)


def split_into_chunks(skeleton: dict) -> list[str]:
    """Extract just the text content for translation."""
    chunks = []
    for block in skeleton["blocks"]:
        if block["type"] in ("heading", "paragraph", "blockquote", "list_item", "numbered_item"):
            chunks.append(block["content"])
        elif block["type"] == "table":
            for row in block["rows"]:
                for cell in row:
                    chunks.append(cell)
        elif block["type"] == "raw":
            chunks.append(block["content"])
    return chunks


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python format_skeleton.py extract input.md --output skeleton.json")
        print("  python format_skeleton.py restore skeleton.json translated.txt --output result.md")
        sys.exit(1)

    command = sys.argv[1]

    if command == "extract":
        input_file = sys.argv[2]
        output_file = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--output" else "skeleton.json"

        text = Path(input_file).read_text(encoding="utf-8")
        skeleton = extract_skeleton(text)
        Path(output_file).write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Extracted {len(skeleton['blocks'])} blocks to {output_file}")

    elif command == "restore":
        skeleton_file = sys.argv[2]
        translated_file = sys.argv[3]
        output_file = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "--output" else "result.md"

        skeleton = json.loads(Path(skeleton_file).read_text(encoding="utf-8"))
        translated_lines = Path(translated_file).read_text(encoding="utf-8").strip().split("\n---CHUNK---\n")
        result = restore_skeleton(skeleton, translated_lines)
        Path(output_file).write_text(result, encoding="utf-8")
        print(f"Restored to {output_file}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

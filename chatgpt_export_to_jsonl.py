#!/usr/bin/env python3
"""
chatgpt_export_to_jsonl.py
--------------------------
Convert a raw OpenAI ChatGPT data export into clean, human-readable files.

Outputs (one or both):
* JSONL — one message per line, machine-friendly:
    {"speaker": "user"|"assistant", "content": "...",
     "timestamp": "<ISO 8601 UTC>", "conversation": "<title>"}
* TXT — one transcript per conversation, easy to read.

Usage:
    # Point at the unzipped export folder OR the zip itself OR conversations.json
    python3 chatgpt_export_to_jsonl.py ~/Downloads/chatgpt-export.zip
    python3 chatgpt_export_to_jsonl.py ~/chatgpt_export/
    python3 chatgpt_export_to_jsonl.py ~/chatgpt_export/conversations.json

    # Optional flags
    --format {jsonl,pretty,both}   default: both
    --out-dir DIR                  default: ./output
    --limit N                      stop after N messages
    --dry-run                      print first 5 entries, write nothing
    --user-name X                  speaker label for "user" role (default: "user")
    --assistant-name Y             speaker label for "assistant" role (default: "assistant")
    --include-system               include "system" role messages too
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


# ---------------------------------------------------------------------------
# Loading the export
# ---------------------------------------------------------------------------

def _load_conversations(source: Path) -> list[dict]:
    """Return the parsed conversations.json list from any supported source."""

    if source.is_file() and source.suffix == ".json":
        with source.open("r", encoding="utf-8") as f:
            return json.load(f)

    if source.is_file() and source.suffix == ".zip":
        with zipfile.ZipFile(source) as zf:
            name = next(
                (n for n in zf.namelist() if n.endswith("conversations.json")),
                None,
            )
            if not name:
                raise SystemExit(f"No conversations.json found inside {source}")
            with zf.open(name) as f:
                return json.loads(io.TextIOWrapper(f, encoding="utf-8").read())

    if source.is_dir():
        candidate = source / "conversations.json"
        if candidate.exists():
            return _load_conversations(candidate)
        raise SystemExit(f"No conversations.json in directory {source}")

    raise SystemExit(f"Unsupported source: {source}")


# ---------------------------------------------------------------------------
# Walking a single conversation
# ---------------------------------------------------------------------------

def _ordered_messages(convo: dict) -> Iterator[dict]:
    """
    Yield message nodes in conversation order by walking from current_node
    back through parent links, then reversing.
    """
    mapping = convo.get("mapping") or {}
    current = convo.get("current_node")
    if not current or current not in mapping:
        for node in mapping.values():
            if node.get("message"):
                yield node["message"]
        return

    chain: list[dict] = []
    seen: set[str] = set()
    node_id = current
    while node_id and node_id in mapping and node_id not in seen:
        seen.add(node_id)
        node = mapping[node_id]
        if node.get("message"):
            chain.append(node["message"])
        node_id = node.get("parent")

    for msg in reversed(chain):
        yield msg


def _extract_text(message: dict) -> str:
    """Pull a clean text payload from a ChatGPT message node."""
    content = message.get("content") or {}
    ctype = content.get("content_type")
    parts = content.get("parts") or []

    if ctype in {"text", "multimodal_text", None}:
        chunks: list[str] = []
        for part in parts:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict):
                txt = part.get("text")
                if txt:
                    chunks.append(txt)
        return "\n".join(c for c in chunks if c).strip()

    if ctype == "code":
        return str(content.get("text", "")).strip()

    if ctype == "user_editable_context":
        return ""

    return ""


def _ts_to_iso(ts: float | int | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return ""


def _slugify(text: str, fallback: str = "conversation") -> str:
    text = (text or "").strip() or fallback
    slug = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return (slug[:60] or fallback).strip("-")


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def iter_conversations(
    conversations: list[dict],
    *,
    user_name: str,
    assistant_name: str,
    include_system: bool,
    limit: int | None,
) -> Iterator[tuple[dict, list[dict]]]:
    """Yield (conversation_meta, [entries]) pairs in source order."""
    emitted = 0
    for convo in conversations:
        title = (convo.get("title") or "").strip() or "Untitled conversation"
        meta = {
            "title": title,
            "create_time": _ts_to_iso(convo.get("create_time")),
            "update_time": _ts_to_iso(convo.get("update_time")),
        }

        entries: list[dict] = []
        for message in _ordered_messages(convo):
            author = (message.get("author") or {}).get("role") or ""
            if author == "user":
                speaker = user_name
            elif author == "assistant":
                speaker = assistant_name
            elif author == "system" and include_system:
                speaker = "system"
            else:
                continue

            text = _extract_text(message)
            if not text:
                continue

            entries.append({
                "speaker": speaker,
                "content": text,
                "timestamp": _ts_to_iso(message.get("create_time")),
                "conversation": title,
            })

            emitted += 1
            if limit is not None and emitted >= limit:
                yield meta, entries
                return

        if entries:
            yield meta, entries


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_jsonl(out_path: Path, all_entries: Iterable[dict]) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_pretty(out_dir: Path, convos: list[tuple[dict, list[dict]]]) -> int:
    """Write one human-readable .txt per conversation. Returns file count."""
    out_dir.mkdir(parents=True, exist_ok=True)
    used: dict[str, int] = {}
    files_written = 0

    for meta, entries in convos:
        if not entries:
            continue
        base = _slugify(meta["title"])
        used[base] = used.get(base, 0) + 1
        suffix = "" if used[base] == 1 else f"-{used[base]}"
        path = out_dir / f"{base}{suffix}.txt"

        with path.open("w", encoding="utf-8") as f:
            f.write(f"# {meta['title']}\n")
            if meta["create_time"]:
                f.write(f"Created: {meta['create_time']}\n")
            if meta["update_time"]:
                f.write(f"Updated: {meta['update_time']}\n")
            f.write("\n" + ("-" * 72) + "\n\n")

            for entry in entries:
                ts = f" [{entry['timestamp']}]" if entry["timestamp"] else ""
                f.write(f"{entry['speaker']}{ts}:\n")
                f.write(entry["content"].rstrip() + "\n\n")

        files_written += 1
    return files_written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("source", type=Path, help="Path to .zip, export dir, or conversations.json")
    p.add_argument("--format", choices=["jsonl", "pretty", "both"], default="both")
    p.add_argument("--out-dir", type=Path, default=Path("output"))
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--user-name", default="user")
    p.add_argument("--assistant-name", default="assistant")
    p.add_argument("--include-system", action="store_true")
    args = p.parse_args(argv)

    print(f"📥 Loading {args.source} ...")
    convos_raw = _load_conversations(args.source.expanduser())
    print(f"   found {len(convos_raw):,} conversation(s)")

    print("🔎 Parsing messages ...")
    convo_pairs = list(iter_conversations(
        convos_raw,
        user_name=args.user_name,
        assistant_name=args.assistant_name,
        include_system=args.include_system,
        limit=args.limit,
    ))
    flat_entries = [e for _, entries in convo_pairs for e in entries]
    total = len(flat_entries)

    if args.dry_run:
        print(f"\n--- DRY RUN: first 5 of {total:,} entries ---\n")
        for entry in flat_entries[:5]:
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        print(f"\n✅ Would have imported {total:,} memories from {len(convo_pairs):,} conversation(s).")
        return 0

    out_dir = args.out_dir.expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.format in {"jsonl", "both"}:
        jsonl_path = out_dir / "imported_memories.jsonl"
        jsonl_count = write_jsonl(jsonl_path, flat_entries)
        print(f"💾 JSONL → {jsonl_path} ({jsonl_count:,} entries)")

    if args.format in {"pretty", "both"}:
        pretty_dir = out_dir / "transcripts"
        pretty_count = write_pretty(pretty_dir, convo_pairs)
        print(f"📜 Pretty → {pretty_dir}/ ({pretty_count:,} transcript file(s))")

    print(f"\n✨ Imported {total:,} memories from {len(convo_pairs):,} conversation(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())

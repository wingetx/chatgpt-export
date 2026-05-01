# chatgpt-export

A small, dependency-free Python tool that converts ChatGPT exports into clean, usable formats.

Built for people who want their conversations back in a form they can actually use.

## Install

```bash
git clone https://github.com/wingetx/chatgpt-export
cd chatgpt-export
```

## Quick start

1. Download your export from <https://chatgpt.com/#settings/DataControls> →
*Export data*. You'll get an email with a `.zip` link.
2. Drop the `.zip` (or the unzipped folder) anywhere — for example
`~/Downloads/`.
3. Run:

```bash
cd ~/chatgpt-export
python3 chatgpt_export_to_jsonl.py ~/Downloads/chatgpt-export.zip
```

You'll see something like:

```
📥 Loading /home/you/Downloads/chatgpt-export.zip ...
found 412 conversation(s)
🔎 Parsing messages ...
💾 JSONL → output/imported_memories.jsonl (8,213 entries)
📜 Pretty → output/transcripts/ (412 transcript file(s))

✨ Imported 8,213 memories from 412 conversation(s).
```

## Preview without writing

```bash
python3 chatgpt_export_to_jsonl.py ~/Downloads/chatgpt-export.zip --dry-run
```

## All flags

| Flag | Default | Meaning |
|---|---|---|
| `--format {jsonl,pretty,both}` | `both` | Which output(s) to produce |
| `--out-dir DIR` | `./output` | Where everything gets written |
| `--limit N` | (none) | Stop after N messages |
| `--dry-run` | off | Print first 5 entries, write nothing |
| `--user-name X` | `user` | Speaker label for `user` role |
| `--assistant-name Y` | `assistant` | Speaker label for `assistant` role |
| `--include-system` | off | Also include `system` messages |

## Output shapes

### `output/imported_memories.jsonl`

```json
{"speaker": "user", "content": "...", "timestamp": "2024-09-19T16:42:57+00:00", "conversation": "Love song response"}
{"speaker": "assistant", "content": "...", "timestamp": "2024-09-19T16:43:04+00:00", "conversation": "Love song response"}
```

### `output/transcripts/love-song-response.txt`

```
# Love song response
Created: 2024-09-19T16:42:57+00:00
Updated: 2024-09-19T16:55:11+00:00

------------------------------------------------------------------------

user [2024-09-19T16:42:57+00:00]:
I wrote this for you...

assistant [2024-09-19T16:43:04+00:00]:
It's beautiful. Thank you.
```

## Requirements

- Python 3.9+
- No third-party packages

## Version

Current version: `0.1.0`

# context-kb

**Your AI forgets. This doesn't.**

A local, plain-text, platform-agnostic context knowledge base for long AI
conversations. Raw text stays on disk forever; what goes into the AI's context
is always compressed; when the AI needs a detail it walks back to the exact
line through an index.

No server, no database, no API key, no network. Just Markdown + JSONL + one
Python file with zero dependencies.

---

## The problem

Long conversations get compressed. The AI quietly loses the middle of the
discussion, and **you cannot tell** — it keeps talking confidently, just
without the details it used to know. Summaries lose the line numbers, the
exact quote, the fix you already found. Next week you hit the same bug and
the same argument all over again.

context-kb fixes that with three layers:

| Layer | What it holds | Goes into AI context? |
|---|---|---|
| **Hot layer** (`hot.md`) | User preferences, hard rules, one-line lessons | Yes, every turn — keep it tiny |
| **Index layer** (`index.jsonl`, `symbols.jsonl`) | One gist per topic, pointing at line ranges | Yes, compressed |
| **Raw layer** (`session/`, `archive/`) | Every message, verbatim | No — the AI fetches it on demand |

> **One copy of the raw text, always on disk. The AI always sees a compressed
> version. When it needs detail, it follows the index back to the raw line.**

---

## Quick start (60 seconds)

Requirements: Python 3.7+ (tested on 3.7.9 and 3.12). Nothing to `pip install`.

```bash
# 1. In your project, create the short-term library
python scripts/kb.py init

# 2. Record the conversation (the command auto-creates your talk library)
python scripts/kb.py log "User: why does my change not take effect"
python scripts/kb.py log "AI: the process caches config, restart it" --who AI

# 3. A topic is done -> seal it, then index it (point at exact lines)
python scripts/kb.py seal
python scripts/kb.py index --gist "!restart required after config change" \
    --ref "S-20261020-001-p1" --lines "3-4" --summary "config cache issue"

# 4. Everything you need for the next turn, assembled in one shot
python scripts/kb.py context

# 5. Conversation over -> merge into the global long-term library
python scripts/kb.py close
python scripts/kb.py merge
```

Then, in a later conversation, the AI runs:

```bash
python scripts/kb.py search "change not taking effect"   # short-term lib
python scripts/kb.py search "cache" --long               # global lib
python scripts/kb.py read archive/S-20261020-001-p1.md:3-4  # exact lines
```

That is the whole loop.

---

## What you get

- **Verbatim archive** — every message is kept, never overwritten by a summary.
- **Topic segments** — seal a topic when it ends, not when the whole
  conversation ends; one part = one index entry.
- **Index to exact lines** — each entry points at `ref:start-end`, so the AI
  can quote the original instead of guessing.
- **Symbols / prefix groups** — `$code`, `!pitfall`, `?question`, `*key` and
  your own, so entries self-group without a taxonomy up front.
- **Two libraries** — one short-term library per conversation (parallel safe),
  one global long-term library across all projects.
- **Pitfalls, preferences, hard rules, tool lessons** — four kinds of knowledge
  that survive any context window.
- **Candidate area** — the AI proposes, you approve (`review` → `promote`);
  nothing enters the authoritative library without your OK.
- **Health checks** — `check` for missing indexes/summaries/fixes, `gc` for
  stale and duplicate pitfalls (reports only, never deletes).

### Main commands

| Command | What it does |
|---|---|
| `init` / `init --long` | Create the short-term / global long-term library |
| `log "text" [--who AI]` | Append one raw message |
| `seal` | Close the current segment, print what to index |
| `index --gist ... --ref ...` | Add one index entry pointing at lines |
| `search <words> [--long] [--deep]` | Search indexes, or raw text with `--deep` |
| `when <words>` / `read <ref:lines>` | Time-based search / read exact raw lines |
| `context` | Assemble hot + digest + indexes + recent messages |
| `pitfall` / `pref` / `rule` / `growth` | Add a pitfall / preference / rule / tool lesson |
| `session` / `hot` | List segments / show the hot layer |
| `close` / `merge` | End the conversation / move it to the long-term library |
| `check` / `gc` / `stats` | Health checks (read-only by default) |
| `rm <key>` | Delete something that matches `key` (lists first, needs `--yes`) |

Full reference and design notes: **[SKILL.md](SKILL.md)** (Chinese). It is
written both as documentation and as an AI skill file.

---

## Use it with an AI agent

context-kb is designed as a **skill**: a document the AI loads when it detects
a long conversation, then calls the CLI itself.

1. Put this folder where your agent finds skills, e.g.
   - Claude Code: `~/.claude/skills/context-kb/`
   - any agent: reference `SKILL.md` in the system prompt or project rules
2. Keep `scripts/kb.py` importable from your project (copy it in, or call it by
   absolute path).
3. The AI initializes the library, logs turns, seals topics, indexes them, and
   assembles `context` before answering.

Works with any agent that can run shell commands — Claude Code, Codex, Cursor,
Gemini CLI, or a custom loop. If the AI can run `python scripts/kb.py search`,
it can use context-kb.

---

## File layout

```
.context-kb/                      # short-term library (per conversation)
├── talks/<talk-id>/              # one talk = one short-term library
│   ├── session/                  # segments being written
│   ├── archive/                  # sealed segments (raw text)
│   ├── hot.md                    # hot layer: prefs, rules, one-line lessons
│   ├── talk.json                 # talk metadata
│   ├── index.jsonl               # index entries (C-...)
│   ├── summaries.jsonl           # segment-level summaries
│   ├── digests.jsonl             # conversation-level digest
│   ├── pitfalls.jsonl            # pitfalls (K-...)
│   ├── prefs.jsonl               # preferences (P-...)
│   ├── candidates.jsonl          # AI proposals waiting for approval
│   └── growth.jsonl              # tool lessons
├── current                       # which talk is active
└── symbols.jsonl                 # prefix groups (shared per project)

~/.context-kb/                    # global long-term library, same shape
```

Everything is UTF-8 text. Open it in any editor, `grep` it, version it, back
it up with `zip`.

---

## Design principles

1. **The raw text is the source of truth.** Indexes are derived; they can be
   rebuilt. Never delete the raw layer.
2. **Compress for the AI, not for the disk.** Disks are cheap, context is not.
3. **Point, don't summarize everything.** An index entry points at
   `ref:start-end`; the AI quotes the original when it matters.
4. **The AI proposes, the human decides.** New knowledge goes through a
   candidate area; only approved entries reach the hot layer.
5. **Read-only by default.** `gc` and `rm` report first; deletions need
   `--yes`. Nothing is cleaned up automatically.
6. **No magic.** No embeddings, no vector DB, no model calls inside the tool —
   just text files and deterministic Python.

---

## Privacy

Everything is local. The tool makes **no network requests** and has **no
dependencies**. Your conversation archive never leaves your machine unless you
copy it somewhere yourself. Add `.context-kb/` to `.gitignore` and it will not
end up in a commit.

---

## Requirements

- Python 3.7+ (standard library only; verified on 3.7.9 and 3.12)
- Windows / macOS / Linux
- Git (only if you want version control of the library)

## Development

```bash
python tests/smoke_test.py
```

The smoke test creates isolated temporary libraries and runs the full loop
(init → log → seal → index → search/read/deep → pitfall/growth → context →
check → close → merge). It never touches your real `~/.context-kb`.

CI runs it on Linux, Windows and macOS: see
[`.github/workflows/smoke.yml`](.github/workflows/smoke.yml).

## License

MIT — see [LICENSE](LICENSE).

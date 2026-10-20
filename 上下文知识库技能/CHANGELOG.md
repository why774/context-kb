# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-20

First public release.

### Added

- Three-layer local knowledge base: hot layer (`hot.md`), index layer
  (`index.jsonl` + `symbols.jsonl`), raw layer (`session/` + `archive/`).
- Two libraries: one short-term library per conversation, one global long-term
  library shared across projects.
- Topic segments: `log` → `seal` → `index --ref ... --lines ...`, with index
  entries pointing at exact line ranges.
- Retrieval: `search` (indexes), `search --deep` (raw text), `when`
  (time-based), `read <ref:lines>`, and `context` (assembly for the AI).
- Long-term knowledge: `pitfall`, `pref`, `rule`, `growth`, plus a candidate
  area with `review` / `promote` / `drop` so the AI proposes and the human
  decides.
- `check` (missing indexes/summaries/fixes), `gc` (stale and duplicate
  pitfalls — report only), `stats`, `rm` (lists first; `--yes` to delete).
- Hit-based sorting of the "long-term lessons" section in the hot layer:
  recent 4 entries plus up to 4 most-hit entries, deduplicated.
- `tests/smoke_test.py`: end-to-end smoke test in isolated temp libraries,
  works on Windows/macOS/Linux, never touches the real `~/.context-kb`.
- CI workflow running the smoke test on Linux, Windows and macOS.
- Verified against the oldest supported runtime, Python 3.7.9, in addition to
  3.12 (CI runs the smoke test on 3.9 and 3.12).

### Fixed

- Short-term library paths: `search`/`when`/`read`/`session`/`check`/`hot`/
  `keywords`/`rm` now resolve `session/` and `archive/` under
  `.context-kb/talks/<talk-id>/`, where the data actually lives. Previously
  they looked in the library root, so those commands silently returned
  nothing in short-term libraries.
- UTF-8 output when stdout is redirected to a file or pipe, while leaving the
  terminal encoding alone so Chinese text renders correctly in legacy Windows
  consoles.
- `SKILL.md` frontmatter now uses the standard YAML skill format.

### Changed

- Directory `工具/` renamed to `scripts/`; all command references updated.
- Documentation split into `README.md` (English), `README.zh-CN.md` (Chinese),
  and `SKILL.md` (the AI skill file, Chinese).

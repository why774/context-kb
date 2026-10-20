# Contributing

Thanks for taking a look. This project is deliberately small: a plain-text
knowledge base, a zero-dependency Python CLI, and one AI-facing spec
(`SKILL.md`). Contributions that keep it small are the most welcome.

## Ground rules

1. **Zero dependencies.** Standard library only, Python 3.7+. No `pip install`,
   no network calls, no model calls. Anything that needs them belongs in a
   different project.
2. **Don't break existing libraries.** Files in `~/.context-kb` and
   `.context-kb/` are plain JSONL. New fields are fine; renaming or removing
   existing ones is a breaking change and needs a migration or a version bump.
3. **Keep the layers separate.** `scripts/kb.py` is a thin CLI shell. Logic
   belongs in `scripts/kbmod/`, one concern per module.
4. **Windows-safe output.** Users run this in legacy consoles; keep stdout
   UTF-8 only when redirected (see the guard in `scripts/kbmod/base.py`) so
   Chinese text does not turn into mojibake or crash on cp936.
5. **`SKILL.md` is the spec.** If user-visible behavior changes, update it and
   `CHANGELOG.md` in the same PR. The tool and the spec must not drift apart.

## Development

There is nothing to install:

```bash
python scripts/kb.py init        # short-term library in the current project
python tests/smoke_test.py       # end-to-end run in isolated temp libraries
```

The smoke test must stay isolated: it points `HOME` / `USERPROFILE` at a temp
directory, so it can never touch the real `~/.context-kb`. Keep it that way.

If you touch the Python path handling, check the oldest supported runtime
(Python 3.7.x) as well — CI only covers 3.9 and 3.12.

## Pull requests

- One concern per PR; small diffs review faster.
- Run the smoke test before opening (and after rebasing).
- Add a `CHANGELOG.md` entry under a new `## [Unreleased]` section when the
  change is user-visible.
- Describe *why* in the PR body; the diff already shows *what*.

## Reporting

Use the issue templates: bug reports with a full command sequence and the exact
output are fixable in minutes; "it doesn't work" is not.

## Code of conduct

Be decent. That is the whole policy.

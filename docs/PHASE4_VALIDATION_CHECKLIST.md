# Phase 4 Validation Checklist

This checklist is the merge gate for the Source-of-Truth implementation. CI must evaluate the exact feature-branch head that will be merged.

- Ruff passes without exclusions added for Phase 4.
- Strict mypy passes for all `tarkov_agent` modules.
- Pytest passes on Windows and Ubuntu with Python 3.12.
- Seeded Scav claims resolve with preserved citations.
- Unknown mechanics return a refusal rather than a guessed value.
- Conflicting overlapping claims block recommendation use.
- Historical values require an explicit patch when patch windows differ.
- Stale material may be displayed for review but cannot authorize a recommendation.
- Markdown and JSON exports retain source, URL, locator, role, patch, and review metadata.
- The first Scav test uses manual raid lifecycle controls; automatic log signatures remain disabled until separately validated.

# Phase 5 Validation Checklist

- Ruff passes without new exclusions.
- Strict mypy passes for all `tarkov_agent` modules.
- Pytest passes on Windows and Ubuntu with Python 3.12.
- A Scav progression request produces at least two mechanically eligible candidates using seeded verified claims.
- An unknown user-supplied hard mechanic blocks every candidate and returns research tasks.
- Patch ambiguity, stale claims, and open conflicts cannot authorize a candidate.
- PPE evidence identifiers survive player-fit evaluation output.
- Missing or disabled PPE produces neutral fit with lower confidence rather than invented traits.
- Progression and training remain separate recommendation purposes.
- Training requests include a controlled experiment design.
- JSON and Markdown exports preserve mechanics, assumptions, blockers, research tasks, and confidence.
- The engine remains pre-raid/post-raid assistance and does not introduce game automation or memory access.

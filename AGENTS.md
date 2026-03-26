# Project Rules

- Keep page-level surfaces transparent. Do not add local background fills or page/root/scroll-area style sheets that block Windows 11 Mica.
- Prefer built-in `qfluentwidgets` appearance over custom page styling. Add local UI styling only when the user explicitly asks for it or when the library cannot provide the needed result.
- Do not force `WA_TranslucentBackground` on full pages, scroll areas, or their viewports unless it is explicitly needed and visually verified; prefer the same built-in page behavior used by working screens.
- After UI changes, rebuild the app and verify it still starts.

<!-- repo-task-proof-loop:start -->
## Repo task proof loop

For substantial features, refactors, and bug fixes, use the repo-task-proof-loop workflow.

Required artifact path:
- Keep all task artifacts in `.agent/tasks/<TASK_ID>/` inside this repository.

Required sequence:
1. Freeze `.agent/tasks/<TASK_ID>/spec.md` before implementation.
2. Implement against explicit acceptance criteria (`AC1`, `AC2`, ...).
3. Create `evidence.md`, `evidence.json`, and raw artifacts.
4. Run a fresh verification pass against the current codebase and rerun checks.
5. If verification is not `PASS`, write `problems.md`, apply the smallest safe fix, and reverify.

Hard rules:
- Do not claim completion unless every acceptance criterion is `PASS`.
- Verifiers judge current code and current command results, not prior chat claims.
- Fixers should make the smallest defensible diff.

Installed workflow agents:
- `.codex/agents/task-spec-freezer.toml`
- `.codex/agents/task-builder.toml`
- `.codex/agents/task-verifier.toml`
- `.codex/agents/task-fixer.toml`
<!-- repo-task-proof-loop:end -->

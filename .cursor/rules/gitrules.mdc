---
description:
globs:
alwaysApply: true
---
- **Branch-per-Task (BPT) strategy**
  - For every Taskmaster task create a dedicated branch:
    `task-<id>-<slug>` (e.g. `task-17-api-metrics-fix`).
  - Base the branch on `master` (or the active feature tag’s branch if using tags).

- **Explicit confirmation before committing**
  - Stage (`git add -A`) **only after tests pass locally**.
  - Ask the user for “OK to commit & push?” before every commit.
    - If *yes*: `git commit -m "<Conventional Commit>"` then `git push -u origin <branch>`.
    - If *no*: keep refining until approval.

- **Atomic, Conventional Commits**
  - One logical change per commit; do not mix refactors with new features.
  - Use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, …).
  - Include Task ID in the footer:
    ```
    feat(api): add /metrics endpoint

    Task: #12
    ```

- **Pull-Request & Merge rules**
  - Open a PR as soon as the first commit is pushed (draft OK).
  - CI must be green (lint, type-check, tests, coverage ≥90 %) before PR can be marked ready.
  - At least one approving review required.
  - **Squash-merge** into `master` to keep history linear; PR title becomes squash commit.

- **CI/CD pipeline tie-ins**
  - `push` or `pull_request` on any branch triggers the **CI matrix** (`.github/workflows/ci.yml`):
    1. Ruff / Black / Mypy linters
    2. Pytest + coverage gate (≥90 %)
    3. Optional perf job (`make perf`) on nightly cron
  - `push` on `master` (post-merge) additionally:
    - Builds & pushes the Docker image to GHCR
    - Uploads nightly `pg_dump` backup artifacts
  - Semantic version tag (`v*.*.*`) triggers Vercel/Supabase deploy workflow when those features land (Task 18).

- **Rebasing & Syncing**
  - Keep branch up-to-date via `git pull --rebase origin master`.
  - Resolve conflicts locally; re-run full test suite before pushing.

- **Large / risky features**
  - If a feature spans several Taskmaster tasks:
    - Create an umbrella branch `feature/<name>` forked from `master`.
    - Open PR targeting `master`, then stack task branches on top and merge sequentially.

- **Emergency fixes**
  - Branch from `master` → `hotfix/<issue>`
    - Fast-track through CI; reviewers may approve retrospectively if blocking production.

- **Tag discipline**
  - Only CI/CD or release scripts create annotated tags (`git tag -a vX.Y.Z -m ...`).

- **Pre-commit hooks (guard rails)**
  - `poetry run pre-commit install` on first clone.
  - Hooks block pushes that violate formatting or lint rules.

- **Documentation & traceability**
  - Link PRs to Taskmaster tasks (`Fixes TM-#<id>`) so the bot can automatically close them.
  - Keep CHANGELOG updated via Changesets if public releases are cut.

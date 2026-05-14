# CLAUDE.md

Project-level instructions for Claude Code. Read on every session.

## Branch workflow

This repo uses a `staging → main` flow. Treat these as hard rules:

- `main` is production. It only receives merges from `staging`. Never push to `main` directly, and never open a PR with `main` as the base.
- `staging` is the integration branch. All feature and fix work merges here first.
- Feature/fix branches must be cut from `staging`, not from `main`.
- **Every PR Claude opens must target `staging` as the base branch.** When using `mcp__github__create_pull_request`, always pass `base: "staging"`. When using `gh pr create`, always pass `--base staging`.
- Only the human opens `staging → main` PRs. Claude does not promote to production.

## Branch naming

- Features: `feature/<short-description>`
- Fixes: `fix/<short-description>`
- Chores/infra: `chore/<short-description>`
- Avoid pushing to `claude/*` branches unless explicitly instructed; prefer the conventional prefixes above.

## Commit and PR style

- Commit messages: conventional-commit style (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`).
- PR titles: short (<70 chars), describe the change not the task.
- PR bodies: include a Summary and a Test plan section.

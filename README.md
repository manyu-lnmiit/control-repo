# control-repo

Orchestration repo for Abhimanyu's fully-autonomous daily project pipeline.

## How it works

1. A scheduled Claude session runs once a day. It picks a fresh project idea
   (Agentic AI / autonomous agents / other currently-relevant AI & software
   engineering topics), builds a complete, production-grade implementation —
   working code, tests, README, CI workflow, Dockerfile, license — and drops
   it into `pending/<YYYY-MM-DD>-<project-slug>/` in this repo, then pushes.
2. That push triggers `.github/workflows/publish.yml`, which runs on GitHub's
   own infrastructure (not a sandboxed environment, so it has normal GitHub
   API access). It creates a brand-new public repo under this account named
   after the slug, pushes the project's contents there as the initial commit,
   and then removes the folder from `pending/` in this control repo.
3. `history.json` keeps a running log of every project shipped (date, slug,
   title, one-line description) so future runs can avoid repeating ideas.

## One-time setup (already done if you're reading this after setup)

- This repo needs a repository secret named `REPO_CREATE_TOKEN` — a GitHub
  Personal Access Token with permission to create repositories under this
  account. Add it under **Settings → Secrets and variables → Actions → New
  repository secret**.

## Nothing else to do

Once the secret is set, the pipeline is fully autonomous: no manual repo
creation, no manual pushes.

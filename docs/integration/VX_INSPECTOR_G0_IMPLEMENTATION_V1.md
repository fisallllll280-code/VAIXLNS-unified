# VX Registry & Execution Inspector — Isolated Implementation v1

## Scope and provenance

- Implementation branch: `feat/vx-inspector-g0-20261021`.
- Source baseline: `4b36bd19c4efea80d5cc22ba0e900ddf7d1d2258`.
- Canonical authority remains `fisallllll280-code/VAIXLNS`, `project.genome` and `Ω.000`.
- No pull request, merge to main, publish operation, canonical rewrite, or external model request is authorized here.
- This instrument is a **read-only observation surface**, not a passed G0 gate.

## Components

| Component | Repository path | Operation |
| --- | --- | --- |
| Inspector | `workspace/vx_inspector.py` | Read local allowed sources, SHA-256, declared federation metadata and provider profiles |
| Dashboard | `workspace/inspector.html` | Responsive Arabic view with model registry, gates, systems, hashes |
| Server | `api/server.py` | `GET /inspector`, `GET /workspace/vx-inspector` |
| Navigation | `workspace/dashboard.html` | Link existing workspace dashboard to inspector |
| Tests | `tests/test_vx_inspector.py` | Zero-budget and side-effect denial, missing paths, hash change, malformed JSON, symlink |
| HTTP tests | `tests/test_vx_inspector_api.py` | API response, UI availability, configured bearer-token requirement |

## Run in a fully isolated local worktree

```bash
git fetch origin main
git worktree add -b test/vx-inspector-validation ../vx-inspector-validation origin/main
cd ../vx-inspector-validation
python -m unittest tests.test_vx_inspector -v
python -m pytest -q tests/test_vx_inspector_api.py
python -m workspace.vx_inspector --root . > /tmp/vx-inspector-observation.json
VAIXLNS_API_TOKEN=<operator-secret> python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```

Navigate to `http://127.0.0.1:8000/inspector`. Enter the API token in the page (not saved in storage).

## Multi-model design

The screen inventories OpenAI, Claude, Gemini, Grok and Mistral provider **candidates**. OpenAI and Claude have existing repository adapter sources. The remaining three adapters require implementation/testing and provider credentials. No model endpoint is contacted here.

- There is no universal "strongest model" assumption. Operator-selected model IDs must be benchmarked per task.
- Credentials presence is not an authorization or connectivity proof.
- The environment has a zero-SAR external spend ceiling; no external inference request is performed.
- A live adapter must prove identity, explicit authority, token limits, input protections, health/probe evidence and license compliance before adoption.
- Obsidian vaults may be mounted through the existing allowlisted local workspace source path, but the inspector itself does not fetch or modify them.

## Gates and stop conditions

The original `VX-INT-EXEC-001` execution sequence remains `T01–T05 -> T06–T10 -> T15 -> T11–T14`. All those formal test IDs are shown as `NOT_RUN`, unless a separate verified execution receipt is explicitly associated. Ordinary inspector unit tests DO NOT qualify as those formal tests.

Proceed only when G0 proves a frozen and authorized source revision, branch protection/merging controls, all canonical aliases and hashes, dependency resolution, isolated worktree, baseline tests and a run-specific test map. A `PASS` CI result for this branch is **not** permission to merge, publish or change the canonical registry.

## Known limitations

- Snapshot reflects locally visible files and configuration declarations, not the entire account or live GitHub state.
- Absence of `project.genome` or `Ω.000` in the unified working tree is expected; inspect their actual canonical repository in the separate G0 process. Do not recreate them here.
- Git blob SHA and SHA-256 are different formats and must be tracked separately.
- GitHub CI must be tied to its exact commit SHA, not presumed to validate later commits.
- The existing Workspace API may run without authentication when `VAIXLNS_API_TOKEN` is unset; bind only to loopback in development and require a token plus additional hardening before remote access.

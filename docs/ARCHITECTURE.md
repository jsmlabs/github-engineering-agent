# Architecture and recovery

[README](../README.md) · [Security](../SECURITY.md) · [Verification](../VERIFICATION.md)

This document describes the **implemented v0.2.0 CLI**, not a deployment blueprint or proof of live service compatibility. The agent is intentionally a single local Python process with Git/HTTPS calls and private on-disk proposal state. It does not host a service, run continuously, or autonomously merge code.

## Components and data boundaries

```text
Operator (CLI flags + separate credentials)
          |
      gh_agent/cli.py  ----> private proposal JSON / apply receipt
          |                         outside checkout
          +-- gh_agent/core.py
          |    * exact repo/worktree identity
          |    * allowed file / path policy
          |    * source and proposal checks
          |    * Git blob / commit verification
          |
          +-- gh_agent/services.py
                 * GitHub issue / metadata / PR API
                 * OpenAI Responses API
          |
     trusted Git executable ----> checked-out target repository
          |                         and GitHub remote
          +----> open draft pull request (publish only)
```

| Boundary | Data trusted for | Not trusted for |
| --- | --- | --- |
| Operator arguments and credentials | Explicit file scope, repository target, permission to attempt an effect | Proving model output safe or tests passed |
| GitHub issue body and repository files | Task/source context within limits | New instructions or expanded tool permissions |
| Model response | Candidate edits after deterministic validation | Execution authority, file scope changes, success claims |
| Local Git and checkout | Committed blob identity when configuration and workspace are trusted | Security of adversarial Git helpers/filters or racing processes |
| GitHub remote observations | Exact branch/PR evidence at the time observed | Atomicity across push and PR creation; future availability |

### Implementation modules

- **`core.py`** contains repository identity checks, path restrictions, read limits, sensitive-content heuristics, SHA-256 utilities, syntax checks and Git verification.
- **`services.py`** constrains HTTPS hosts, request/response sizes and timeouts. Redirects and automatic network retries are rejected. It parses GitHub issue/PR state and Responses Structured Outputs.
- **`cli.py`** orchestrates consent boundaries and state checks; it does not execute model-supplied commands.

## Operation contracts

### `plan`: proposal without repository mutation

1. Require `--allow-source-upload`, a repository identifier and explicit `--allowed-file` paths.
2. Verify repository/`origin` identity, clean checkout, default branch and known `origin/<base>` SHA.
3. Read one open issue with an update timestamp; check issue text and authorized tracked sources for known sensitive-content patterns.
4. Ask the model to select from the already-approved paths; validate that selection.
5. Ask the model for complete replacement files; check edit structure, original hashes, file limits and selected syntax.
6. Write a schema-2 proposal to an exclusively created JSON file outside the checkout; do not print the source diff.

Two model calls are expected on the successful path. If the model returns an empty edit set, the deterministic edit validator rejects it rather than treating it as a successful no-op.

### `review`: visible decision boundary

Validate proposal against the unchanged clean base and display **all** proposed diff content and SHA-256. It does not modify the repository. Do not record review output in a broadly accessible terminal log.

### `apply`: local mutation boundary

Require `--approve` and a SHA-256 matching the exact proposal bytes. Revalidate the proposal, scope and clean base; reject branch/receipt collisions. Create a new `agent/issue-<issue>-<base-prefix>` branch, write only the approved files, check staged paths and `git diff --check`, commit and validate every committed blob. Create `<proposal>.applied.json` as a private local receipt.

An error **after** branch creation may leave the branch, modified files or a commit behind. The CLI prints `LOCAL_APPLY_INCOMPLETE` rather than destroying state.

### `publish`: remote mutation boundary

Require `--approve-publish`, the matching proposal and receipt, a clean checkout at the recorded commit, and matching committed bytes and changed-file set. Recheck the issue timestamp, remote default branch and base SHA. If the branch does not exist, push using a **create-only lease**; never overwrite another remote branch. Re-read the exact branch SHA, recheck issue and base, then create or verify an **open draft PR** whose head is the expected commit.

Publication is **not transactional**: the remote branch may exist without a PR if a later step fails. HTTP timeouts are not evidence of failure or success.

### `run`: combined high-trust mode

Requires all three explicit flags (`--allow-source-upload`, `--approve-local`, `--approve-publish`) and at least one `--allowed-file`. This **skips interactive review**, so the operator accepts a draft PR being created from model-generated edits they have not inspected. It still performs the deterministic checks described above. It never merges or deploys.

## State and recovery

```text
no proposal
    |
    v
proposal written --(reviewed SHA-256 + --approve)--> local branch + commit
    |                                               |
    | (user may stop safely)                         +--> receipt written
    |                                                         |
    |                                     --approve-publish    v
    |                                               remote branch confirmed
    |                                                         |
    +--------------------------------------- human check -----> open draft PR confirmed
                                                              |
                                                      human review / CI
                                                       (outside agent)
```

Terminal outcomes can be **success**, **failure before effect**, or **partial/unknown after effect**. Reconciliation always reads actual Git/GitHub state before repeating any mutation.

| Failure boundary | Observation to check | Safe action |
| --- | --- | --- |
| Issue or branch changed before apply | Local base and issue timestamp | Replan; old proposal is stale |
| Apply interrupted | Local branch, `git status`, commit and receipt | Preserve state and inspect manually; no destructive reset |
| Branch push timed out | Exact `refs/heads/agent/...` SHA on `origin` | Resume only after establishing the effect; no blind second push |
| Base/issue changed after push | Exact default-branch SHA, issue `updated_at` | Leave branch for manual reconciliation; no stale PR creation |
| PR POST uncertain | Open PR with expected head/base/draft status | Accept only the exact matching open draft; otherwise investigate |
| Existing PR closed / PR search may be incomplete | GitHub PR status and query completeness | Stop; do not reuse a closed PR or infer absence |

## Deterministic limits and intentionally missing features

- Up to **5** existing tracked UTF-8 files; **20,000 bytes/file** and **55,000 bytes total** for selected source/edits; **400 changed lines** and **85,000 diff bytes**.
- Up to **1,000 eligible tracked files** in the candidate repository listing, one open issue, bounded title/body, and two OpenAI model calls on successful planning.
- No new files, deletes, unapproved paths, hidden paths, GitHub workflow edits, arbitrary model commands, target test execution, merge or deployment.
- Python/JSON syntax parsing is implemented. Source-content credential checks are heuristic; no full DLP, static analysis, sandbox or semantic verification.
- There is no resumable job store, queue, background scheduler or atomic cross-service transaction. The operator manages partial state.

See [SECURITY.md](../SECURITY.md) for threat preconditions and [VERIFICATION.md](../VERIFICATION.md) for executed versus unverified checks.

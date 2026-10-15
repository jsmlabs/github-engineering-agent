# GitHub Engineering Agent

**Version 0.2.0 · Bounded, local, issue-to-draft-PR engineering agent**

A standalone Python CLI for proposing and applying narrowly scoped changes to an *existing, trusted Git checkout* in response to a GitHub issue. It uses OpenAI Responses Structured Outputs for proposals, and deterministic Python/Git checks for path policy, source authorization, file integrity, syntax, state, and remote effects.

> **Assurance level:** locally tested reference implementation, **not production validated**. It is not an unattended general-purpose software engineer. Real OpenAI calls, GitHub authentication, network publishing, repository CI, security review, and deployment were **not** tested during development. It never merges or deploys.

## Capabilities and explicit boundaries

| Command | Effect | Operator approval |
| --- | --- | --- |
| `plan` | Read one open issue and explicitly allowed tracked files; make 2 model requests; write a private JSON proposal | `--allow-source-upload` + at least one `--allowed-file` |
| `review` | Validate clean base, source checksums and scope; display complete proposed diff | Read-only |
| `apply` | Revalidate proposal, make a local branch and commit exactly the authorized files | `--approve` + SHA-256 of the inspected proposal |
| `publish` | Reconcile remote SHA and issue version; push the exact commit; create/verify **draft** PR | `--approve-publish` |
| `run` | Execute bounded `plan → apply → publish` without an inspection pause | `--allow-source-upload --approve-local --approve-publish` and explicit file scope |

The autonomous `run` command **is a deliberate high-trust mode**: it may publish AI-generated code as a draft PR without human inspection of the specific edit. Draft PR is *not* merge authorization, security approval or proof of code correctness. Prefer `plan → review → apply → publish` for normal use.

No model-generated commands are executed. The program does not merge, approve reviews, deploy, inspect secrets, run arbitrary tests or alter workflows. Repository Git configuration, credential helpers, external code and issue descriptions can still be unsafe: run in an isolated checkout and review before trust-sensitive use.

## Prerequisites

- Python **3.11+** and Git in `PATH`.
- A **dedicated clean Git checkout** of the intended repository, on its default branch at the checked-out `origin/<default>` SHA. Fetch and inspect the remote manually first.
- `origin` fetch **and** push URLs must point to the exact `https://github.com/OWNER/REPO[.git]` or supported GitHub SSH equivalent; no additional push URLs.
- `GITHUB_TOKEN`: least-privileged repository token with Issues: read, and, for publishing, Contents: write and Pull requests: write; an existing secure Git credential helper or SSH identity for push.
- `OPENAI_API_KEY`: an API credential. Choose a model supporting Responses `text.format` JSON-schema Structured Outputs and sufficient output context. Verify availability, data policies and prices yourself.
- A secure local path **outside the target checkout** for the proposal JSON. It contains the full replacement text of selected files.

Only **existing tracked UTF-8 files** may be authorized in v0.2.0. At most 5 files, at most 20 KB per file, 55 KB total, 400 changed lines, and an 85 KB textual diff. Unsafe paths, symlinks, excluded directories, secret-like names and suspected embedded credentials are rejected. These heuristics are **not comprehensive secret scanning** or a semantic security analyzer.

## Install

From the extracted project directory:

```bash
python -m pip install --no-build-isolation .
python -m gh_agent --help
python scripts/verify.py
```

Or run directly without installation: `python -m gh_agent --help`. The CLI has no external runtime Python dependencies.

Provide credentials using your operating system's supported secret management mechanisms or environment variables. **Never put a token into the proposal JSON, source code or a Git remote URL.**

## Recommended step-by-step workflow

From a terminal with credentials available, and with a dedicated checkout already fetched and clean:

```bash
python -m gh_agent plan \
  --repo OWNER/REPO --issue 123 \
  --checkout /absolute/path/to/trusted/checkout \
  --model YOUR_STRUCTURED_OUTPUT_MODEL \
  --allowed-file src/feature.py \
  --allowed-file tests/test_feature.py \
  --allow-source-upload \
  --output /private/location/issue-123.json

python -m gh_agent review \
  --checkout /absolute/path/to/trusted/checkout \
  --proposal /private/location/issue-123.json

# Inspect full diff and policy effects first. Next step writes a local branch and commit:
python -m gh_agent apply \
  --checkout /absolute/path/to/trusted/checkout \
  --proposal /private/location/issue-123.json \
  --expected-sha256 COPY_SHA256_FROM_REVIEW \
  --approve

# Independently run the project's tests in a trusted/sandboxed environment,
# inspect the commit and obtain any required review/approval before publishing.
python -m gh_agent publish \
  --checkout /absolute/path/to/trusted/checkout \
  --proposal /private/location/issue-123.json \
  --approve-publish
```

`review` prints the exact proposal SHA-256 and the full proposed diff. Copy that digest into `apply --expected-sha256` after inspection; editing the proposal invalidates the approval. In deliberate `run` mode, the digest is computed automatically because the operator has explicitly accepted publication without per-proposal human inspection. `review` prints source text to your terminal; avoid log aggregation for sensitive projects. `plan` displays only paths and metadata by default (not a source diff). The proposal is created exclusively with mode `0600`, subject to filesystem semantics.

### Unattended-to-draft mode (opt-in)

```bash
python -m gh_agent run \
  --repo OWNER/REPO --issue 123 \
  --checkout /absolute/path/to/trusted/checkout \
  --model YOUR_STRUCTURED_OUTPUT_MODEL \
  --allowed-file src/feature.py \
  --output /private/location/issue-123.json \
  --allow-source-upload --approve-local --approve-publish
```

All authorizations are operator-provided CLI flags. The repository URL, issue number and exact eligible files cannot be expanded by an issue body or model instruction. This does **not** ensure the edited code is safe or correct. Use only on isolated, low-risk scopes with required PR review and CI gates.

## Deterministic controls

1. **Repository identity:** compare `origin` URLs, default branch, local HEAD and clean working tree. Reject protected/hidden paths and symlinks.
2. **Scope:** require repeatable `--allowed-file PATH`. The model sees only these path names and selected source files; any different selection or edit is rejected.
3. **Privacy:** explicit data-upload consent; block common token/private-key patterns in allowed source, issue and generated output. This is a deny heuristic, *not* a guarantee of detecting all secrets.
4. **Validation:** strict proposal format, original-source SHA-256, byte/diff budgets, Python `ast.parse`, JSON parsing, `git diff --check`, exact changed-path comparison, and exact committed Git blob bytes.
5. **Binding:** proposal schema v2 includes operator-approved paths; manual apply requires the SHA-256 of the inspected proposal; the receipt records the SHA-256 of the file at commit time. A different proposal file is rejected before remote effects. This is **not a tamper-proof signature** against a local attacker who can rewrite both files.
6. **Remote effects:** before publishing, verify exact remote ref names, the issue timestamp and base SHA. New remote branches use a create-only Git lease so concurrent branch creation cannot be overwritten; the base and issue are rechecked before PR creation. Reject ambiguous PR result pages and closed PR collisions; reconcile ambiguous push outcomes by reading remote refs. Require an **open draft** PR matching the expected commit.
7. **Resource bounds:** at most two model requests, fixed per-request timeout and content limits, one issue, one bounded commit, no automatic network mutation retries, no merge/deploy capability.

### State and recovery

```text
proposed → reviewed → authorized → local_commit
       → remote_branch_verified → open_draft_pr_verified
           ↘ failed | partial | unknown → manual reconciliation
```

- Local apply errors preserve the new branch/worktree for inspection; there is **no destructive reset**.
- If push times out, the agent checks the remote ref before deciding whether the effect occurred. An unresolved outcome requires manual review, not blind replay.
- A closed PR using the same branch is a collision, not an existing successful draft. Incomplete PR search pages also fail closed.
- Outdated base, updated issue, altered proposal or changed commit state blocks publish.
- A successful draft PR does not imply passing project tests, adequate security review, CI, mergeability or production readiness.

## Files

- `gh_agent/core.py` - path policy, source checks, repository identity, proposal integrity, Git object verification.
- `gh_agent/services.py` - bounded GitHub/OpenAI REST clients, JSON-schema proposals.
- `gh_agent/cli.py` - `plan`, `review`, `apply`, `publish`, `run` control flow.
- `tests/test_agent.py` - deterministic no-network tests with temporary repositories and mocked external services.
- `scripts/verify.py` - reproducible local compile, CLI and test-suite checks.
- `SECURITY.md` - threat model, limits, incident handling.
- `CHANGELOG.md` - release changes and compatibility notes.

## Verification

```bash
python scripts/verify.py
```

Runs Python compilation, all unit tests and CLI smoke checks. Tests are local/fixture-based; the test suite does not contact a real GitHub repository or OpenAI account. Do not represent successful offline checks as operational validation of a deployed agent.

## Compatibility and known limitations

- **Proposal schema 2:** proposals from v0.1.0 (`schema: 1`) are intentionally **not accepted** by `apply` or `publish`. Replan under explicit file scope. Receipts are not migrated.
- No sandbox execution of generated code, test runner, code reviewer, background task scheduler, webhook receiver, persistence database, cryptographic approval log or distributed worker queue.
- No semantic proof that edits respect business invariants. Scope and syntax checks are necessary but insufficient.
- Git hooks are suppressed where supported, but an untrusted Git installation, credential helper, config filters, external tooling or locally competing writer remains an operational risk. Do not run in an untrusted worktree.
- File operations are not transactional and a crash between commit and receipt can require manual recovery.
- Source/issue heuristics cannot identify every private value; users must independently review data-sharing permissions and applicable privacy rules. ASCII terminal-control characters are rejected, but rendered Markdown and model-generated prose still require independent review.
- Parsing Python and JSON is not executing target tests. For JS, TS, YAML and other languages, syntax validation requires trusted external tooling not included here.
- Real GitHub response semantics, rate limits, configured branch protection and model behavior must be revalidated against live services prior to production use. Test coverage includes one local bare Git server for create-only push-lease behavior, not real GitHub PR creation.

## Release verification record

See [VERIFICATION.md](VERIFICATION.md) for the exact local checks, observed environment, evidence scope, and what has **not** been verified.

## Context and API references

- [`AI Agent Execution Contracts`](https://github.com/jsmlabs/chatgpt-context/blob/main/knowledge/ai-agent-execution-contracts.md)
- [`Agent Workflow Architect`](https://github.com/jsmlabs/chatgpt-context/blob/main/prompts/agent-workflow-architect.md)
- [`Repository Engineering Execution`](https://github.com/jsmlabs/chatgpt-context/blob/main/instructions/repository-engineering-execution.md)
- [`Verification Engineering`](https://github.com/jsmlabs/chatgpt-context/blob/main/instructions/verification-engineering.md)
- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [GitHub REST API versioning](https://docs.github.com/en/rest/about-the-rest-api/api-versions)

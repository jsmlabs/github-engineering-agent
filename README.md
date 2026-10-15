<div align="center">

# GitHub Engineering Agent

**AI proposes. Deterministic controls decide. Humans authorize.**

A minimal Python CLI that turns one GitHub issue into a bounded, inspectable code proposal and, after explicit approvals, a **draft pull request**.

[![Offline verification](https://github.com/jsmlabs/github-engineering-agent/actions/workflows/offline-verification.yml/badge.svg)](https://github.com/jsmlabs/github-engineering-agent/actions/workflows/offline-verification.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Package version 0.2.0](https://img.shields.io/badge/package-0.2.0-64748b)
![Reference implementation](https://img.shields.io/badge/maturity-reference%20implementation-64748b)

[Quick start](#quick-start) · [Workflow](#how-it-works) · [Commands](#command-reference) · [Safety](#safety-boundaries) · [Docs](#documentation)

</div>

> [!IMPORTANT]
> **Reference implementation, not production-validated automation.** The CLI can create a local commit and publish an **open draft PR**, but it cannot review, approve, merge, or deploy code. The default offline test suite does **not** exercise live OpenAI/GitHub operations or an actual Docker daemon. See [verification evidence](VERIFICATION.md).

## What it does

| Stage | Operator control | Observable artifact |
| :--- | :--- | :--- |
| **Plan** one open issue and 1–5 explicitly approved tracked files | Explicit source-upload consent and exact file allowlist | Private proposal JSON, no working-tree changes |
| **Review** proposed full-file replacements | Inspect unified diff and proposal SHA-256 | Decision to approve or stop |
| **Apply** locally | `--approve` + exact `--expected-sha256` | New branch, Git commit, private receipt |
| **Verify** optional target tests | Operator-supplied digest-pinned Docker image and command | Commit-bound PASS/FAIL record |
| **Publish** a draft | `--approve-publish` + passing verification **or** explicit no-test exception | Create-only remote push and confirmed **open draft PR** |

No model-generated shell command is executed. GitHub workflow files, hidden paths, secrets, new files, deletions, unapproved paths, automatic merging, and deployment are outside this product's supported scope.

## How it works

~~~mermaid
flowchart LR
    A["Open issue + approved tracked files"] --> B["plan"]
    B --> C["review: full diff + SHA-256"]
    C --> D{"Approve?"}
    D -->|No| X["Stop"]
    D -->|Yes| E["apply: local commit"]
    E --> F["verify: optional isolated tests"]
    F --> G{"Publication gate"}
    G -->|PASS| H["publish: draft PR"]
    G -->|No test record + explicit exception| H
    G -->|FAIL / stale| Y["Blocked"]
    H --> I["External review + CI"]
~~~

**Recommended:** `plan → review → apply → verify → publish`. The opt-in `run` command combines stages **without pausing for proposal-specific human review**; it still requires distinct authorizations and a verification plan or explicit no-test exception.

## Quick start

### 1. Prepare an isolated checkout

You need Python **3.11+**, Git, a clean dedicated checkout of the **target** repository at its fetched default-branch commit, and an absolute private proposal path **outside** that checkout.

Set credentials in your environment using your approved secret manager:

| Credential | When needed | Minimum expected capability |
| --- | --- | --- |
| `GITHUB_TOKEN` | Reading issue/repository metadata and PR API | Issues **read** for planning; publishing also requires Contents **write** and Pull requests **write** |
| Git push credential | Publishing the new branch | Separate authorized SSH identity or Git credential helper |
| `OPENAI_API_KEY` | Planning | Access to a Responses API model supporting strict JSON-schema Structured Outputs |

The Git `origin` fetch and push URLs must exactly identify `OWNER/REPO` and contain no embedded credentials. Avoid shared or untrusted worktrees and concurrent writers. **Classify issue/source data before permitting provider upload.**

### 2. Install and run offline checks

~~~bash
python -m pip install .
python -m gh_agent --help
python scripts/verify.py
~~~

Run these from a checkout of **this** agent repository. The CLI can also be invoked as `gh-engineer` after installation. Runtime Python dependencies are limited to the standard library; package installation may need build tooling. `scripts/verify.py` runs compilation, offline tests and CLI help only.

### 3. Plan and review

Replace placeholders with a real **open issue**, existing tracked paths, and a supported model. The following commands use POSIX shell continuation; Windows users may place each command on one line.

~~~bash
python -m gh_agent plan \
  --repo OWNER/REPO --issue 123 \
  --checkout /absolute/target-checkout \
  --model YOUR_STRUCTURED_OUTPUT_MODEL \
  --allowed-file src/feature.py \
  --allowed-file tests/test_feature.py \
  --allow-source-upload \
  --output /private/issue-123.json

python -m gh_agent review \
  --checkout /absolute/target-checkout \
  --proposal /private/issue-123.json
~~~

`plan` makes two model requests on a successful path. It uploads issue text and selected source content only after `--allow-source-upload`, then exclusively creates a private schema-2 proposal file (mode `0600` where supported). It does not print the proposed source diff. `review` prints the **entire diff and proposal digest**; protect terminal logs.

### 4. Approve and apply the exact proposal

~~~bash
python -m gh_agent apply \
  --checkout /absolute/target-checkout \
  --proposal /private/issue-123.json \
  --expected-sha256 COPY_EXACT_DIGEST_FROM_REVIEW \
  --approve
~~~

`apply` rechecks the clean base, authorized paths and content, then creates `agent/issue-<issue>-<base-sha-prefix>`, commits the approved replacements, validates committed Git blobs and exclusively writes `/private/issue-123.json.applied.json`. **A digest is not a signature** against someone who can alter both local proposal and receipt.

### 5. Verify, then publish

`verify` runs only a command **you supply** in a trusted, preloaded digest-pinned image. It requires a POSIX host, a trusted isolated Docker daemon, and a read-only mount of the checkout; native Windows Docker verification is not supported.

~~~bash
python -m gh_agent verify \
  --checkout /absolute/target-checkout \
  --proposal /private/issue-123.json \
  --image registry.example/test-image@sha256:YOUR_64_HEX_DIGEST \
  --command-json '["python","-m","unittest","discover","-s","tests"]' \
  --timeout 120

python -m gh_agent publish \
  --checkout /absolute/target-checkout \
  --proposal /private/issue-123.json \
  --approve-publish
~~~

`verify` creates `/private/issue-123.json.verified.json` tied to the proposal SHA and commit. A recorded **FAIL or stale report always blocks publication**. If **no verification record exists**, `publish` can instead accept `--approve-unverified` together with a substantive `--unverified-reason` (12–300 characters); this exception does not override a failure.

`publish` rechecks the issue timestamp, default branch, base commit, file set, committed bytes, remote refs and existing PR. It uses a **create-only Git push lease**, then verifies an **open draft PR** with the expected head. Remote push and PR creation are **not atomic**.

## Command reference

| Command | Mode | Key required options / safeguards |
| --- | --- | --- |
| `plan` | Reads issue/source and writes proposal | `--repo`, `--issue`, `--checkout`, `--model`, `--allowed-file` (repeatable), `--output`, `--allow-source-upload` |
| `review` | Read-only proposal/diff inspection | `--checkout`, `--proposal` |
| `apply` | Local branch, file edits and commit | `--checkout`, `--proposal`, `--expected-sha256`, `--approve` |
| `verify` | Operator-configured isolated test | `--checkout`, `--proposal`, `--image`, `--command-json`; optional `--timeout` (1–300 s, default 120) |
| `status` | Read-only local recovery; optional remote lookup | `--checkout`, `--proposal`; optional `--remote` |
| `publish` | New remote branch and draft PR | `--checkout`, `--proposal`, `--approve-publish`; existing PASS or explicitly justified no-test exception |
| `run` | High-trust combined flow | Plan options plus `--approve-local`, `--approve-publish` and either test options or explicit no-test exception |

### Reviewed flow vs. high-trust `run`

| Property | Reviewed flow | `run` |
| --- | --- | --- |
| Stops for review of generated proposal | **Yes** | **No** |
| Exact operator-approved file scope | Required | Required |
| Explicit source/local/remote permissions | At each relevant step | All required up front |
| Test configuration or no-test exception | Required before publishing | Required before planning |
| Highest automatic remote effect | **Draft PR** | **Draft PR** |

~~~bash
python -m gh_agent run \
  --repo OWNER/REPO --issue 123 \
  --checkout /absolute/target-checkout \
  --model YOUR_STRUCTURED_OUTPUT_MODEL \
  --allowed-file src/feature.py \
  --output /private/issue-123.json \
  --allow-source-upload --approve-local --approve-publish \
  --test-image registry.example/test-image@sha256:YOUR_64_HEX_DIGEST \
  --test-command-json '["python","-m","unittest","discover","-s","tests"]'
~~~

> [!WARNING]
> `run` may commit and publish **unreviewed model-generated changes as a draft**. Use it only in a tightly controlled, explicitly authorized environment with independent downstream code review. It never merges or deploys.

## Safety boundaries

| Area | Enforced limit or behavior |
| --- | --- |
| Target files | 1–5 distinct, existing tracked, non-hidden UTF-8 files from an explicit allowlist |
| Source/edit budget | 20,000 bytes/file; 55,000 total bytes; 400 changed lines; 85,000-byte proposal diff |
| Repository/issue | At most 1,000 eligible tracked candidate files; one open issue, maximum 6,000-character body and required revision timestamp |
| Source validation | Approved relative paths, symlink checks, original SHA-256, Python/JSON syntax parsing, secret heuristics, committed-blob comparison |
| JSON boundaries | Duplicate keys and non-finite constants rejected across untrusted API/model/state JSON; unexpected model output parts fail closed |
| Remote effects | Exact remote identity and refs; no overwrites; issue/base rechecks; expected **open draft PR** |
| Verification | Operator-supplied pinned image and argv; constrained POSIX-host Docker invocation; missing tests require explicit exception |
| Outside scope | Arbitrary model commands, new/deleted files, workflow edits, review approval, merge, deployment, automatic target-test discovery |

Checks are **not** proof of semantic correctness, complete secret detection, a safe Docker daemon, live API compatibility or production readiness. See [Security policy](SECURITY.md).

## Recovery

Use read-only status before attempting to recover interrupted operations:

~~~bash
python -m gh_agent status \
  --checkout /absolute/target-checkout \
  --proposal /private/issue-123.json --remote
~~~

| What happened | Safe response |
| --- | --- |
| Checkout dirty or base changed | Inspect Git state; preserve unrelated work; replan from a verified base |
| Proposal SHA mismatch | Inspect the modified proposal, review again and require fresh explicit approval |
| `LOCAL_APPLY_INCOMPLETE` | Inspect branch, working tree, commit and receipt; no automatic rollback |
| Test record missing | Run operator-selected tests or explicitly justify a no-test exception |
| Test failure or stale record | Stop publication; investigate rather than override |
| Push timed out or PR request failed | Compare exact remote branch SHA and open PR head/base/draft state before retrying |
| Closed PR, conflicting branch or incomplete PR search | Stop and reconcile manually; never reuse uncertain state |

See [Architecture & recovery](docs/ARCHITECTURE.md) for state transitions and failure handling.

## Documentation

| Document | Scope |
| --- | --- |
| [Architecture & recovery](docs/ARCHITECTURE.md) | Component boundaries, state machine, local and remote failure recovery |
| [Security](SECURITY.md) | Threat model, approvals, credentials, isolation, residual risk, incident response |
| [Verification](VERIFICATION.md) | Commit-specific CI evidence, test reproduction, unverified capabilities |
| [Changelog](CHANGELOG.md) | Unreleased hardening, package releases and compatibility notes |

**Implementation entry points:** [CLI](gh_agent/cli.py) · [core policy](gh_agent/core.py) · [API clients](gh_agent/services.py) · [verification](gh_agent/verification.py) · [offline tests](tests/test_agent.py) · [check runner](scripts/verify.py).

**Compatibility:** Package version `0.2.0` requires Python 3.11+. Current proposals/receipts use **schema 2**; verification reports use **schema 1**. Proposal/receipt schema 1 from v0.1.0 cannot be used with v0.2.0; create a new scoped plan. There is no automatic migration, job queue, hosted service, scheduling or merge/deployment workflow.

**Background references (non-normative):** [AI Agent Execution Contracts](https://github.com/jsmlabs/chatgpt-context/blob/main/knowledge/ai-agent-execution-contracts.md) · [Agent Workflow Architect](https://github.com/jsmlabs/chatgpt-context/blob/main/prompts/agent-workflow-architect.md) · [Repository Engineering Execution](https://github.com/jsmlabs/chatgpt-context/blob/main/instructions/repository-engineering-execution.md) · [Verification Engineering](https://github.com/jsmlabs/chatgpt-context/blob/main/instructions/verification-engineering.md).

**Upstream APIs:** [OpenAI Responses](https://developers.openai.com/api/reference/resources/responses/methods/create) · [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) · [GitHub REST](https://docs.github.com/en/rest/about-the-rest-api/api-versions). Revalidate supported models, authentication, API versions and policies before live use.

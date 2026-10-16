<div align="center">

# GitHub Engineering Agent

**From an issue to a reviewable pull request — with explicit control at every step.**

A lightweight Python CLI for scoped AI-generated edits, deterministic validation, local approval, and draft or review-ready GitHub publication.

[![Offline verification](https://github.com/jsmlabs/github-engineering-agent/actions/workflows/offline-verification.yml/badge.svg)](https://github.com/jsmlabs/github-engineering-agent/actions/workflows/offline-verification.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Unreleased development metadata v0.3.0.dev5](https://img.shields.io/badge/package-0.3.0.dev5--unreleased-64748b)
![Reference implementation](https://img.shields.io/badge/maturity-reference-64748b)

**`plan` → `review` → `apply` → `verify` → `publish`**

[**Start in terminal**](#start-in-terminal) · [**Quick start**](#quick-start) · [**Workflow**](#workflow) · [**Commands**](#command-reference) · [**Safety**](#safety-model) · [**Documentation**](#documentation)

</div>

> [!IMPORTANT]
> **Reference implementation — not a production-validated autonomous engineer.** The agent can create an approved local commit and an **open pull request**. It does **not** approve reviews, merge, or deploy. Offline tests do not establish live OpenAI/GitHub compatibility, target-code correctness, or real Docker isolation. See [Verification](VERIFICATION.md).

## Local installation and maintenance (preview)

The repository includes an **offline, user-scoped installation manager** for a trusted local Python wheel. It does **not** discover releases, download artifacts, install Python or Git, create shortcuts or automatically update from `main`. Use Python 3.11+ and verify the wheel checksum **independently** before installation.

~~~bash
python scripts/setup_check.py --json
python scripts/installer.py preview --wheel /path/to/release.whl --sha256 EXPECTED_64_LOWERCASE_HEX
python scripts/installer.py install --wheel /path/to/release.whl --sha256 EXPECTED_64_LOWERCASE_HEX
python scripts/installer.py verify
python scripts/installer.py repair --wheel /path/to/release.whl --sha256 EXPECTED_64_LOWERCASE_HEX
python scripts/installer.py update --wheel /path/to/new-release.whl --sha256 EXPECTED_64_LOWERCASE_HEX
python scripts/installer.py rollback
python scripts/installer.py status
python scripts/installer.py launch --agent-args gui
python scripts/installer.py uninstall --confirm UNINSTALL
~~~

On Windows, double-click `install-windows.cmd` to maintain the installation or `run-agent.cmd` to start the active agent. On macOS/Linux, use `sh ./install-unix.sh` or `sh ./run-agent.sh`. These launchers require preinstalled Python/Tk and never download the application or dependencies. The maintenance GUI offers a **Preview** action to validate release metadata and local install state without changes, and an **Environment** check for local Python, Git, Docker and credential presence. It does not validate remote access or show secret values. On a graphical workstation, use `python scripts/installer_gui.py` for Install, Update/Repair, Verify and Uninstall actions. It uses OS Tkinter when available and runs operations off the UI thread. The maintenance window validates the full 64-character hexadecimal checksum format before starting wheel-dependent actions and reports action-specific success or failure. A matching checksum alone does not authenticate a publisher. The managed directory defaults to the user's local application-data location. Installing into an existing unmarked directory is refused; uninstall requires a marker and refuses unexpected top-level files. The application keeps its normal explicit CLI permissions and does not prompt for or store credentials. Interactive launches remain active until the application exits; the 240-second timeout applies to installation/verification subprocesses, not the running GUI or menu.

**State validation:** Managed installation state (`state.json`) rejects duplicate JSON keys, nonstandard numeric constants, boolean schema versions, missing required fields and files over 256,000 bytes. Invalid state prevents install/update/rollback until inspected; it is not repaired or overwritten automatically.

**Limitations:** Installation uses separate per-wheel virtual environments and atomically activates verified releases. The previous release remains available for rollback; interrupted installs can leave incomplete inactive environments that require repair. This is not a signed automatic updater or a substitute for live desktop/E2E verification. See [installation guidance](docs/INSTALLATION.md).

## Start in terminal

Install once from **this agent repository** using `python -m pip install .`. Then open a terminal in the **target** repository's clean Git checkout. The installed command is `gh-engineer` (or `python -m gh_agent`).

~~~text
gh-engineer
gh-engineer gui
gh-engineer menu
gh-engineer workspace
gh-engineer files --search app
gh-engineer recipes
gh-engineer commands
gh-engineer guide
gh-engineer doctor --repo OWNER/REPO
~~~

| Command | Simple purpose | Side effects |
| --- | --- | --- |
| `gh-engineer` | Show the short home screen | None |
| `gh-engineer gui` | Desktop window with status, file selection, plan preview and help | Local only; read-only; requires OS Tkinter/Tk and a graphical display |
| `gh-engineer menu` | Numbered terminal menu for local checks, workflow guidance and status | Only local, read-only inspection; never runs a model or publishes |
| `gh-engineer workspace --json` | Check branch, clean worktree, credential presence and Docker CLI without contacting any service | Local read-only inspection; no credential values printed |
| `gh-engineer files --search app --limit 20` | Show eligible existing tracked paths for exact `--allowed-file` selection | No file contents or provider requests |
| `gh-engineer recipes --topic scope` | Show copyable task examples with approval warnings | No commands are executed |
| `gh-engineer prepare --help` | Validate scope and preview a future `plan` argument array, without executing it | No model call, file write or upload approval |
| `gh-engineer commands --group inspect` | Browse/search commands with their side-effect labels; `--json` for scripts | None |
| `gh-engineer dashboard --proposal ../issue-123.json` | Inspect validated local progress with blocked/stale-state detection; `--json` for scripts | Local read-only inspection; remote publication is never assumed |
| `gh-engineer guide` | Show five review-first steps and copyable examples | None |
| `gh-engineer doctor --repo OWNER/REPO` | Check Python, Git, clean checkout and exact origin; credentials are presence-only | Local inspection; no network |
| `gh-engineer next --proposal ../issue-123.json` | Suggest a safe next step from exact local proposal/receipt/verification state | Read-only; does not run the step |
| `gh-engineer status --proposal ../issue-123.json` | Examine the recorded local state | Read-only; `--remote` adds GitHub lookups |

**Graphical desktop app:** run `gh-engineer gui` (or `python -m gh_agent gui`) from the target checkout. The optional Tkinter window provides **Overview**, **Files**, **Plan preview** and **Help** tabs, file/directory pickers and clear local status output. It uses the existing read-only CLI validation, does not start a web server, and cannot upload sources, commit, or publish. Some operating systems require installing an OS Tk/Tkinter package or a graphical display; `gh-engineer menu` remains the fallback. Use `--checkout` and `--proposal` for initial paths. **The GUI preview is not approval to upload**; sensitive source must still be reviewed before invoking the CLI with explicit consent.

**Desktop usability:** The read-only result panel offers **Copy result** and **Clear result** actions, retains Unicode characters in structured output, and shows file multiselection feedback (1–12 paths).  The interface includes scrollable result and file views, four keyboard-accessible tabs (`Ctrl+1` through `Ctrl+4`), a file-list double-click shortcut, and a **Copy result** button (or `Ctrl+Shift+C`); the Files search field accepts **Enter**. Status text distinguishes completed checks from validation failures, and truncated searches indicate when to narrow the query. Refreshing a search clears previously selected paths, and a checkout change requires selecting paths again before plan preview. These are local inspection conveniences, not additional authorizations.

**Interactive menu:** run `gh-engineer menu` in a regular terminal, choose a number from 0–10, and optionally provide a proposal JSON path. Choices include Guide, Doctor, Next step, Local status, Commands and a validated Proposal Dashboard. Choose **Workspace** for the Git preflight summary, **Prepare** to enter an explicitly scoped plan preview, **Files** to search eligible tracked paths or **Recipes** for examples. The file finder shows at most 50 paths per request and never reads their contents. Protected, unsupported and untracked paths are excluded. New files must be scoped explicitly in `prepare`; appearing in the file finder does not prove that uploading a file is safe. The preview returns JSON arguments, **not a shell command**; only a subsequent separately approved `plan --allow-source-upload` can send source data. The menu remembers the previous path only until exit; `0` or `q` quits. Use `gh-engineer menu --no-color` or set `NO_COLOR` for plain text. If standard input/output is not a terminal (CI, piping or automation), use `gh-engineer guide` or the individual commands instead. No extra package or curses dependency is required. Use `gh-engineer commands --search approval` or `--group work` to find an action; use `gh-engineer dashboard --proposal ../issue-123.json --json` for stable machine-readable stage data. `VERIFIED_LOCAL` means only that the saved commit-bound test report passed; an actual remote PR and its CI are **not** confirmed. `BLOCKED` means a recorded test failure or invalid report cannot be treated as a publishing pass.

Find exact file paths and browse recipes without revealing file contents:

~~~bash
gh-engineer files --search src --limit 20
gh-engineer files --json
gh-engineer recipes --topic scope
gh-engineer recipes --json
~~~

The file finder uses the same local tracked-path eligibility checks as the agent, but does not assess all secrets or the suitability of sending content to a provider. Its output is a discovery aid, never an upload approval. `--repo OWNER/REPO` additionally checks the local checkout origin and requires a clean worktree.

Example preview (does not contact GitHub/OpenAI or create a proposal):

~~~bash
gh-engineer prepare --repo OWNER/REPO --issue 123 --model MODEL --allowed-file src/app.py --output ../issue-123.json
gh-engineer workspace --repo OWNER/REPO --json
~~~

`prepare` only works from a clean checkout matching the explicit GitHub origin and existing parent directory for a new proposal path outside checkout. It checks exact allowed file paths, but does not fetch or confirm that the issue is open. The returned arguments deliberately omit `--allow-source-upload`, which is required later by the actual `plan` command.

The current checkout is assumed by default; add `--checkout /path/to/repo` when operating elsewhere. `plan`, `apply`, `verify` and `publish` **still require** their separate authorizations. `doctor` cannot prove credentials work or attest to the Git executable or Docker daemon. Use `gh-engineer COMMAND --help` for every option.

## At a glance

| 🔒 Explicit scope | 🧾 Verifiable changes | 🔀 Scoped PR delivery |
| :--- | :--- | :--- |
| One **open issue** and **1–12 exact existing/new paths** chosen by the operator. | Review a full diff and exact SHA-256 before authorizing a local commit. | A separate approval gates the create-only push and **open PR**. |
| Model-generated text cannot expand permissions. | Verification is bound to a specific proposal and commit. | No automatic review approval, merge, or deployment. |

**Choose your mode**

| | **Reviewed workflow** · recommended | **`run`** · high-trust |
| :--- | :--- | :--- |
| Human inspects generated proposal before edits | **Yes** — `review` + exact-digest approval | **No** — permissions granted up front |
| Operator-controlled file scope | Required | Required |
| Testing before publication | PASS report, or explicit no-test exception | Same gate |
| Maximum remote side effect | **Open PR** | **Open PR** |

## Workflow

~~~mermaid
flowchart TD
    I["Open issue + approved files"] --> P["1. PLAN · Private proposal"]
    P --> R["2. REVIEW · Diff + SHA-256"]
    R --> A{"Approve exact proposal?"}
    A -->|No| STOP["Stop · No local edits"]
    A -->|Yes| L["3. APPLY · Local commit"]
    L --> V["4. VERIFY · Operator-selected test"]
    V --> G{"Publication gate"}
    G -->|PASS| D["5. PUBLISH · Open PR"]
    G -->|No test report + explicit exception| D
    G -->|FAIL or stale| BLOCK["Stop · Publication blocked"]
    D --> H["Independent human review + target CI"]
~~~

**Trust boundary:** The model only **proposes file contents**. The Python/Git layer enforces scope, approvals, validation and remote-state checks. The diagram shows the reviewed path; `run` skips the review pause, **not** the deterministic gates.

## Quick start

### 1. Prepare the environment

You need **Python 3.11+**, **Git**, and a clean trusted checkout of the **target repository**, aligned with its fetched default-branch commit. Store private proposal files at an absolute path **outside that checkout**.

| Credential | Used for | Requirements |
| --- | --- | --- |
| `GITHUB_TOKEN` | Issue/repository/PR REST API | **Issues: read** for planning; **Contents: write** and **Pull requests: write** for publication |
| Git credential | Branch push | Separately configured authorized SSH key or credential helper |
| `OPENAI_API_KEY` | Structured model requests | A Responses API model supporting strict JSON-schema Structured Outputs |

Use a trusted, isolated workspace. The target `origin` fetch/push URLs must identify the exact `OWNER/REPO`. Do not embed tokens in remote URLs, shell arguments or proposal files. **Review data sensitivity before authorizing source upload.**

### 2. Install the CLI and check it offline

Run from a checkout of **this agent repository**:

~~~bash
python -m pip install .
python -m gh_agent --help
python scripts/verify.py
~~~

GitHub Actions runs the offline checks on Ubuntu, macOS and Windows with Python 3.11/3.13, plus Python 3.12 on Ubuntu. These checks do **not** replace authenticated provider or real Docker end-to-end validation.

The installed entry point is also `gh-engineer`. The runtime uses Python's standard library; package installation may require build tooling. `scripts/verify.py` checks compilation, offline unit tests and CLI help — **not live services**.

**Packaging verification:** `python scripts/verify_package.py` builds a wheel from a disposable source snapshot without contacting package indexes, inspects wheel metadata and CLI entry points, installs into a temporary isolated virtual environment, and tests both `python -m gh_agent --help` and `gh-engineer --help`. A separately reported three-OS CI packaging matrix complements the seven existing offline unit-test jobs. CI first bootstraps exact-version, SHA-256-hash-pinned build tools from the package index; the wheel build and temporary installation then run with indexes disabled. No wheel is published, and passing checks do not prove publisher provenance or live model/GitHub compatibility.

### 3. Plan, inspect and approve

Replace the placeholders below with a real open issue, operator-approved **existing or new** paths, an accessible model and private absolute paths.

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

`plan` makes **one** model request on a successful path and writes a private proposal (schema **2**) without printing the generated source diff. `review` prints the complete diff and the proposal file's SHA-256. Protect review transcripts.

~~~bash
python -m gh_agent apply \
  --checkout /absolute/target-checkout \
  --proposal /private/issue-123.json \
  --expected-sha256 COPY_EXACT_DIGEST_FROM_REVIEW \
  --approve
~~~

`apply` creates a new local `agent/issue-<issue>-<base-sha-prefix>` branch and commit, validates the committed bytes, and writes a private `.applied.json` receipt. **The approval digest binds the reviewed proposal, but is not a digital signature against a malicious local host.**

### 4. Verify the commit and publish a pull request

Use a trusted, **already available** digest-pinned Docker image with a test command **you choose**. Verification requires a trusted POSIX host and isolated Docker daemon; native Windows Docker verification is **unsupported**.

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

Add `--ready-for-review` to `publish` or `run` only when the operator specifically wants an **open review-ready PR** rather than the default draft. This does not approve, merge or deploy code.

A commit-bound verification **PASS** allows publication. The isolated test command runs against a **writable disposable copy** of the checkout; the original remains untouched. A recorded **FAIL** or stale report **always blocks** it. Publishing rechecks the issue, base SHA, files and remote branch; the push uses a **create-only lease** and the resulting **open PR** is verified.

<details>
<summary><strong>When testing is unavailable: explicit no-test exception</strong></summary>

Only if **no verification report exists**, the operator can explicitly accept the risk of an unverified pull request. A reason of **12–300 characters** is required; a known test failure cannot be overridden.

~~~bash
python -m gh_agent publish \
  --checkout /absolute/target-checkout \
  --proposal /private/issue-123.json \
  --approve-publish \
  --approve-unverified \
  --unverified-reason "Trusted test image unavailable on this worker"
~~~

</details>

<details>
<summary><strong>Advanced: `run` without proposal-specific human review</strong></summary>

> [!WARNING]
> `run` may commit and publish **unreviewed AI-generated changes** as a pull request. Use it only with explicit source, local and remote authorizations, a constrained checkout and independent downstream review. It cannot merge or deploy. **GitHub Actions workflow edits are not supported in `run`; use `plan → review → apply` with exact-digest approval instead.**

~~~bash
python -m gh_agent run \
  --repo OWNER/REPO --issue 123 \
  --checkout /absolute/target-checkout \
  --model YOUR_STRUCTURED_OUTPUT_MODEL \
  --allowed-file src/feature.py \
  --output /private/issue-123.json \
  --allow-source-upload \
  --approve-local --approve-publish \
  --test-image registry.example/test-image@sha256:YOUR_64_HEX_DIGEST \
  --test-command-json '["python","-m","unittest","discover","-s","tests"]'
~~~

Without both test options, `run` requires an explicit `--approve-unverified` and `--unverified-reason` **before planning**. It can stop after a partial local or remote side effect; inspect state before retrying.

</details>

*The examples use POSIX shell line continuation (`\`). On Windows CMD, put each command on one line or use CMD-appropriate continuation. CLI usage is otherwise cross-platform except for the POSIX-only Docker verification step.*

## Command reference

| Command | What happens | Explicit control |
| --- | --- | --- |
| `menu`, `files`, `recipes`, `commands`, `dashboard`, `workspace`, `prepare`, `guide`, `doctor`, `next` | Menu, catalog, local dashboard, workspace readiness, scoped plan preview and guidance | No automatic edits, provider calls or publication |
| `plan` | Read one issue/allowed source; save private proposal | `--repo`, `--issue`, `--checkout`, `--model`, repeatable `--allowed-file`, `--output`, `--allow-source-upload` |
| `review` | Display full diff + proposal digest; no mutation | `--checkout`, `--proposal` |
| `apply` | Local branch, commit and receipt | `--checkout`, `--proposal`, `--approve`, `--expected-sha256` |
| `verify` | Test exact commit in operator-configured Docker | `--checkout`, `--proposal`, `--image`, `--command-json`, optional `--timeout` |
| `status` | Read-only local recovery, optional remote check | `--checkout`, `--proposal`, optional `--remote` |
| `publish` | Create-only remote push and open PR (draft by default; `--ready-for-review` optional) | `--checkout`, `--proposal`, `--approve-publish` + PASS or explicit exception |
| `run` | Approved combined path without review pause | Planning options, `--approve-local`, `--approve-publish`, test plan or explicit exception |

For supported options, run `gh-engineer COMMAND --help`. The CLI assumes `--checkout .` if omitted; explicit `--checkout` paths remain fully supported.

## Safety model

| Boundary | Enforced contract |
| --- | --- |
| **Files** | 1–12 explicitly scoped existing/new UTF-8 files; new directories, lock/config and named `.github/workflows` files supported; secrets and symlinks denied |
| **Budgets** | 32,000 bytes per file; 96,000 total; 1,600 changed lines; 180,000-byte proposal diff |
| **Inputs** | One open issue, bounded body (12,000 characters), required revision timestamp; exact allowlist instead of candidate-tree limit |
| **Validation** | Original SHA-256, allowed paths, Python/JSON syntax, strict JSON parsing (duplicate keys, overflowed numbers and malformed Unicode), source-secret heuristics, Git staged/committed blob checks |
| **Model** | No execution of model-proposed commands; refuse unexpected/refused/incomplete structured responses |
| **Remote** | Exact repo/ref identity, stale-state rechecks, collision refusal, draft by default or `--ready-for-review` |
| **Verification** | Commit-bound record and strictly typed numeric exit code; explicit no-test exception only when there is no test report |
| **Excluded** | Automatic PR approval, merge, deployment, arbitrary model commands, file deletion and renames |

> [!CAUTION]
> Strict validation does **not** establish generated-code correctness, comprehensive DLP, safe Git/Docker dependencies, vendor compatibility or production readiness. Independent security review and target-project tests are required. Read the [security model](SECURITY.md) and [verification evidence](VERIFICATION.md).

## Recovery and troubleshooting

Before retrying an interrupted action, inspect without changing state:

~~~bash
python -m gh_agent status \
  --checkout /absolute/target-checkout \
  --proposal /private/issue-123.json --remote
~~~

| Observation | Recommended response |
| --- | --- |
| Dirty checkout or stale base | Inspect local changes and remote history; preserve unrelated work and replan |
| Proposal SHA mismatch | Review again and approve the **new exact digest** |
| `LOCAL_APPLY_INCOMPLETE` | Inspect branch, worktree, commit and receipt; **no automatic rollback** |
| Verification FAIL or stale record | Stop publication and investigate; do not override |
| Remote push/PR outcome unknown | Verify exact remote branch SHA and PR head/base/draft state **before retrying** |
| Closed PR, conflicting branch, incomplete search | Stop and manually reconcile |

Remote push and PR creation are **not atomic**; a pushed branch may exist without its PR. See [Architecture & recovery](docs/ARCHITECTURE.md#failure-and-recovery-matrix).

## Documentation

| Guide | Contents |
| --- | --- |
| [Architecture & recovery](docs/ARCHITECTURE.md) | Components, state transitions, artifact schemas and recovery |
| [Security](SECURITY.md) | Threat boundaries, permissions, isolation, incident response |
| [Verification](VERIFICATION.md) | Commit-specific CI results, offline evidence, live gaps |
| [Changelog](CHANGELOG.md) | Unreleased improvements, package history and compatibility |

**Source:** [CLI](gh_agent/cli.py) · [Policy & Git](gh_agent/core.py) · [HTTP & model](gh_agent/services.py) · [Docker verification](gh_agent/verification.py) · [Tests](tests/test_agent.py) · [Offline runner](scripts/verify.py).

**Worker recovery:** Unexpected local worker errors now yield a generic actionable failure instead of leaving the desktop permanently busy. During a running check, a second file search no longer clears an existing scoped selection. Closing is explicitly blocked until the current bounded check has completed.

**Desktop responsiveness:** Local GUI inspections now execute in a bounded, isolated Python subprocess on a worker thread; Tkinter receives results on its own event loop. Only one inspection runs at a time and stale file searches are discarded. This does not add remote approvals or execution capabilities.

**Compatibility:** Unpublished development package metadata **0.3.0.dev5** (previous release baseline **0.2.0**), Python **3.11+**, standard-library runtime. Proposals/receipts use **schema 2**; verification reports use **schema 1**. Old v0.1.0/schema-1 proposals cannot be reused; no automatic migration is provided. No hosted service, scheduler, automatic target-test discovery, merge or deployment.

<details>
<summary><strong>Engineering references and upstream APIs</strong></summary>

**Non-normative context:** [AI Agent Execution Contracts](https://github.com/jsmlabs/chatgpt-context/blob/main/knowledge/ai-agent-execution-contracts.md) · [Agent Workflow Architect](https://github.com/jsmlabs/chatgpt-context/blob/main/prompts/agent-workflow-architect.md) · [Repository Engineering Execution](https://github.com/jsmlabs/chatgpt-context/blob/main/instructions/repository-engineering-execution.md) · [Verification Engineering](https://github.com/jsmlabs/chatgpt-context/blob/main/instructions/verification-engineering.md).

**Upstream:** [OpenAI Responses](https://developers.openai.com/api/reference/resources/responses/methods/create) · [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) · [GitHub REST](https://docs.github.com/en/rest/about-the-rest-api/api-versions). Revalidate API versions, model availability, permissions and data-handling policies before live use.

</details>

---

<div align="center">

**Scoped changes. Explicit consent. Verifiable PR delivery.**

<sub>Reference implementation · No automatic merge or deployment</sub>

</div>

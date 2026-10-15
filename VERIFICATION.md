# Verification and evidence

[← README](README.md) · [Architecture](docs/ARCHITECTURE.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md)

> [!IMPORTANT]
> **Evidence ledger, not certification.** A green offline test matrix verifies the checks that actually ran for **that commit**. It does not prove authenticated OpenAI/GitHub integration, safe generated code, trusted Docker execution or production readiness.

## Latest verified baseline

**Verified baseline: integrated security fixes in `main`, PR #17.**

| Item | Observed evidence |
| --- | --- |
| Authoritative `main` commit | [`45d49e3436cc53cf8cbc38df43463ba394d09bcd`](https://github.com/jsmlabs/github-engineering-agent/commit/45d49e3436cc53cf8cbc38df43463ba394d09bcd) |
| Offline workflow on that commit | [Run 38815112621](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38815112621): **completed / success** |
| Matrix | **6/6 successful jobs**: Ubuntu, macOS and Windows × Python 3.11/3.13 |
| Concrete test observation | Ubuntu/Python 3.13 job: **67 tests, OK**, followed by `LOCAL_VERIFICATION_PASS (offline only)` |
| Commands executed by workflow | `python scripts/verify.py` → Python compilation, `unittest discover`, CLI `--help` |
| Product release metadata | `pyproject.toml` version **0.2.0**, Python **3.11+**, no runtime package dependencies |
| Live API/daemon test | **Not observed**; see [verification gaps](#remaining-verification-gaps) |

The snapshot SHA and workflow identify the **last integrated `main`** before PR #18. PR #18's new capability boundaries are **not** established by the previous main-branch run and require independent head-sha testing and review.

## Recent change evidence

| Scope | PR-head CI | Integrated target-branch evidence | What it establishes |
| --- | --- | --- | --- |
| [#12 strict JSON](https://github.com/jsmlabs/github-engineering-agent/pull/12) | [38809280416](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38809280416), **6/6 pass** | [38809470388](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38809470388), **success** on `afb17a292c3e4979a1a77a6fbb431c69d51a9228` | Local state, API/model JSON and source JSON parsing regressions in the offline suite |
| [#13 CI action pinning](https://github.com/jsmlabs/github-engineering-agent/pull/13) | [38809679328](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38809679328), **6/6 pass** | [38809884465](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38809884465), **success** on `e1f63c573ef30467cef54e801175818dd000595b` | SHA-pinned official GitHub Actions function in the configured matrix |
| [#14 model/recovery hardening](https://github.com/jsmlabs/github-engineering-agent/pull/14) | [38810108472](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38810108472), **6/6 pass** | [38810284708](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38810284708), **success** on `5c698720bc6de352d08e83b6d790fbeb9d14a757` | Offline regressions for model output, outbound JSON and recovery handling |
| [#15 documentation refresh](https://github.com/jsmlabs/github-engineering-agent/pull/15) | [38812066285](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38812066285), **6/6 pass** | [38812223896](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38812223896), **success** on `48eed2ab94909e0232937b3db3ed6351351a570e` | Documentation-only structure and navigation alongside unchanged source tests |
| [#16 README visual refresh](https://github.com/jsmlabs/github-engineering-agent/pull/16) | [38813390691](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38813390691), **6/6 pass** | [38813621301](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38813621301), **success** on `1001bbf3390f171186d8feb4ebbaf49463530492` | Documentation-only presentation improvements |
| [#17 JSON hardening](https://github.com/jsmlabs/github-engineering-agent/pull/17) | [38814929977](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38814929977), **6/6 pass** | [38815112621](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38815112621), **success** on `45d49e3436cc53cf8cbc38df43463ba394d09bcd` | Offline regressions including overflowed numbers, Unicode validation and bounded state JSON |
| Older reference integration | N/A | [38798940522](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38798940522), **success** on `b3b7d871a8f7b36d9ce09dc8f3310ff0fc989f5a` | Earlier verification/recovery implementation's offline workflow |

**Important distinction:** PR and merge activity performed by a GitHub maintainer or separate integration tooling is **not** an authenticated end-to-end test of this CLI's own `publish` method.

## Reproduce the offline checks

Run from a trusted checkout of this repository with Python 3.11+ and Git:

~~~bash
python scripts/verify.py
python -m unittest discover -s tests -v
python -m gh_agent --help
~~~

`scripts/verify.py` runs: (1) `python -m compileall -q gh_agent tests`, (2) verbose unittest discovery, then (3) `python -m gh_agent --help`. It exits nonzero on a failed command.

The default tests use temporary Git repositories and test doubles for network/model behavior. They do not require GitHub/OpenAI tokens or a live Docker daemon. The configured GitHub Actions workflow runs these checks on **six** OS/Python combinations, with read-only repository permission, non-persistent checkout credentials, SHA-pinned actions and a 15-minute job timeout.

### Evidence classification

| Label | Required evidence |
| --- | --- |
| **Executed and passed** | Identified command or CI job, commit, environment and observed success |
| **Offline simulated** | Unit tests with mocks, fixtures or local temporary Git remotes |
| **Not tested** | No observed corresponding runtime call or environment |
| **Inferred from implementation** | Code review supports intended controls but live behavior remains unproven |
| **Not a guarantee** | All results: no finite test suite establishes complete security or semantic correctness |

## Historic checks (retained for provenance)

| Milestone | Observed result | Limitation |
| --- | --- | --- |
| Initial v0.2.0 package validation, 2026-10-15 | Linux, Python 3.13.5, Git 2.47.3; **38/38** offline unit tests, compile and CLI help | No authenticated GitHub/OpenAI calls or target-project CI |
| Initial package build | Clean ZIP extraction/offline checks; offline wheel build/install/import reported **PASS** | Historical environment only; not re-executed in this documentation change |
| Earlier documentation revision | `scripts/verify.py` **38/38 PASS**, local-link checks (32 links/3 fragments), CLI examples inspected | Results apply only to that prior revision |
| Issue #1 malformed PR response | Reproduced unhandled `AttributeError` on malformed nested PR fields; **40/40** after fix | Mocked GitHub responses, no live corrupted response |
| Docker mount-path regression | Negative tests reject actual newline, carriage return and comma in Docker mount paths before subprocess launch | Real Docker invocation not exercised |
| Reconciliation of duplicate PR results | Offline negative test rejects multiple matching PR records | No proof against remote races or pagination beyond returned page |
| Verification gate development | Offline tests cover Docker flags, commit-bound reports, PASS/FAIL gate and mock publication/recovery | No real Docker daemon or full live provider workflow |

Historic results are preserved as historical evidence, **not** as current measurements or independent proof of the latest SHA.

## Unreleased engineering-capability validation

Proposed PR #18 adds explicitly approved new files/directories and configuration/workflow edits (with workflow edits excluded from unreviewed `run`), expanded bounded changes, one model call per plan, a writable disposable verification workspace and opt-in review-ready PRs. The historic tests and workflow results above apply **only** to their listed commits, not automatically to these changes. The first actual CI result for the new head must be recorded after observation; authenticated provider and real Docker execution remain separate unverified capabilities.

## Remaining verification gaps

| Capability | Current evidence status | Required validation before relying on it |
| --- | --- | --- |
| Live OpenAI Responses Structured Outputs with a chosen model | **Not verified** | Authorized live request, refusal/incomplete cases, budget and API response compatibility |
| Authenticated GitHub issue, push and draft PR workflow | **Not verified end-to-end via CLI** | Controlled test repository, least-privilege credentials, actual remote reconciliation and permission/rate-limit behavior |
| Actual Docker `verify` invocation | **Not verified** | Trusted POSIX host and rootless/isolated daemon, pinned image, timeout/cleanup/failure checks |
| Generated code correctness and target project's test suite | **Not verified** | Independent code review, applicable target tests, CI and branch policies |
| Realistic secret/DLP and vulnerability detection coverage | **Not verified** | Threat assessment and negative tests in the intended operating environment |
| Branch protection, concurrency and adverse production races | **Not verified end-to-end** | Explicit scenarios against permitted test repos with current rules |
| Native Windows Docker verification | **Unsupported** | POSIX execution host required; Windows offline test suite is supported |
| Automatic PR approvals, merge, deployment | **Outside product scope** | Must be implemented and governed by a separate authorized system, if ever required |

## Interpretation and maintenance

- **Supported by current CI:** offline Python compilation, deterministic test fixtures, CLI help and the configured platform matrix for the stated SHA.
- **Supported by source review but not proven live:** limited side effects, draft publication checks, resource bounds and error reconciliation.
- **Not established:** production readiness, arbitrary-repository safety, authenticated vendor integration, semantic validity of model-generated changes or exhaustive security coverage.

When implementation or docs change, append a **commit-specific** evidence entry only after checking the actual workflow run. Record success, pending, failure or unavailable accurately. Do not replace historic observations or misstate test counts.

The operating contracts live in [Architecture](docs/ARCHITECTURE.md), [Security](SECURITY.md), and the [version history](CHANGELOG.md).

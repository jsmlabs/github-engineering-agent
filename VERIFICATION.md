# Verification and evidence record

[README](README.md) · [Architecture](docs/ARCHITECTURE.md) · [Security](SECURITY.md)

This is an **evidence log**, not a certification. Separate a check that ran from an inference about behavior that was **not** exercised. A successful fixture test, build or CLI smoke test does not prove a live GitHub/OpenAI workflow is correct or safe.

## Reference release: v0.2.0 (2026-10-15)

The reference package was validated on **Linux**, **Python 3.13.5**, **Git 2.47.3**. No real OpenAI request, authenticated GitHub mutation, target-project CI or deployment was part of that release validation.

| Executed check | Recorded outcome | Evidence scope |
| --- | --- | --- |
| `python -m compileall -q gh_agent tests` | **PASS** | Python compilation only |
| `python -m unittest discover -s tests -v` | **38/38 PASS** | Deterministic offline tests |
| `python -m gh_agent --help` | **PASS** | CLI smoke / argument surface |
| `python -m gh_agent apply --help` | **PASS** | Approval flag discoverability |
| Temporary local bare-Git push lease | **PASS** | Create-only lease rejects a competing local Git ref |
| Mocked GitHub draft PR publication/retry | **PASS** | Reconciliation with simulated service responses |
| Combined CLI `run` with model/GitHub stubs | **PASS** | Stubbed end-to-end control flow, not real external integration |
| Clean ZIP extraction and offline checks | **PASS** | Packaged source can be extracted and tested |
| Offline wheel build, install and import | **PASS** | Local Python packaging compatibility in observed environment |

## Documentation-only update (2026-10-15)

This documentation revision reorganizes usage, security, architecture and limitations **without changing Python code, CLI flags, proposal schema, or package version**. Follow-up validation results should be reported against the actual revision and executed commands, rather than inheriting the reference release's results automatically.

| Check | Scope | Result |
| --- | --- | --- |
| `python scripts/verify.py` | Compilation, 38 offline tests, CLI help | **PASS** - 38/38 tests in this session |
| Markdown local links and fragments | 5 Markdown files, 32 local links, 3 fragments | **PASS** - local link/anchor checker |
| Documented command names/flags | 5 CLI examples compared to parser `--help` | **PASS** - valid documented options |
| Final Git diff / changed paths | README, SECURITY, VERIFICATION, CHANGELOG, new architecture guide | **PASS** - documentation-only, confirmed by Git path review |

The completed change should record the exact resulting GitHub commit and outcome in the PR/commit report; the historic v0.2.0 release outcomes remain separate.

## Issue #1: fail-closed PR-response validation (2026-10-15)

This bounded pilot addresses malformed GitHub pull-request search data. Prior to the fix, a response with `head: null` raised an unhandled `AttributeError`; after the fix, malformed records are rejected as `AgentError`. Valid matching, nonmatching and closed PR behavior remains covered.

| Check | Outcome | Limit |
| --- | --- | --- |
| Reproduction against previous implementation | **REPRODUCED** | `AttributeError` from malformed nested PR fields |
| `python scripts/verify.py` after patch | **PASS - 40/40** | Offline tests, compile, CLI help |
| New PR-record regression tests | **PASS - 2 tests** | Simulated malformed and well-formed GitHub responses |
| Actual GitHub response corruption and live publish | **NOT TESTED** | No authenticated end-to-end CLI run |

No new Python dependency, version change, schema change or automatic merge/deployment was introduced. The test results refer to the changed source tree, not to the original v0.2.0 release.

## Integrated main branch CI (2026-10-15)

The model-response hardening from PR #3 and the verification/recovery changes were integrated through PR #2 into `main` at `b3b7d871a8f7b36d9ce09dc8f3310ff0fc989f5a`. GitHub Actions workflow run [38798940522](https://github.com/jsmlabs/github-engineering-agent/actions/runs/38798940522), triggered by that commit, reports **completed / success** for the offline verification workflow. This establishes the workflow's recorded outcome for that SHA only, not a live Docker verification, end-to-end authenticated GitHub/OpenAI operation, or production readiness.

## Explicitly not verified

| Concern | Evidence status |
| --- | --- |
| OpenAI Responses Structured Outputs with a live chosen model | **NOT VERIFIED** |
| Authenticated GitHub issue/PR APIs, push permissions, rate limits | **NOT VERIFIED** |
| GitHub branch-protection/ruleset behavior and concurrent production updates | **NOT VERIFIED** |
| Generated code semantic correctness, target-project tests or CI | **NOT VERIFIED** |
| Real-world secret detection coverage or vulnerability assessment | **NOT VERIFIED** |
| Native Windows/macOS operation | **NOT VERIFIED** |
| Review approval, merge or deployment | **NOT PERFORMED** |

## Reproduction

In a dedicated checkout with Python 3.11+ and Git installed:

```bash
python scripts/verify.py
python -m unittest discover -s tests -v
python -m gh_agent --help
```

The default offline test suite uses temporary repositories and test doubles; it does **not** need GitHub or OpenAI credentials. Use explicit live integration tests and a representative target project **before** claiming operational readiness. A live PR must still be assessed against the target's security, tests, approvals and policy gates.

## Acceptance interpretation

- **Verified locally:** the particular compile, CLI, packaging and fixture contracts recorded above for the observed environment.
- **Partially supported:** design intent for bounded side effects and reconciliation, based on implementation and local regressions.
- **Not verified:** production reliability, arbitrary-repository correctness, live vendor/permission compatibility and complete security.

Reference documents: [Security](SECURITY.md), [Architecture](docs/ARCHITECTURE.md), and the release changes in [CHANGELOG.md](CHANGELOG.md).


## Docker bind-mount path regression (2026-10-15)

The Docker runner now checks actual newline and carriage-return characters in the checkout mount path, not literal backslash sequences. A regression test asserts that such paths and comma-containing paths are rejected before subprocess execution. The updated PR head must pass its own CI checks; earlier green CI runs apply to previous commits only. A real Docker daemon invocation remains untested in this session.

## Verification-gate development history

This branch adds a digest-pinned Docker test runner, commit-bound verification records, a publication gate, explicit unverified exceptions, read-only status and additional mocked failure-path tests. Docker execution is not exercised by the offline suite; its launch flags and failure handling are unit-tested with stubs. The repository's offline matrix now targets Linux, macOS and Windows on Python 3.11 and 3.13.

**At the time this development note was prepared:** no real Docker test or authenticated GitHub/OpenAI end-to-end run had been observed. Subsequent `main` CI evidence is recorded above; the earlier 40/40 local result is not a substitute for commit-specific CI.

## Ambiguous PR-reconciliation regression (2026-10-15)

A targeted change makes `GitHub.existing_pr` reject multiple matching open PR records instead of silently trusting the first. One offline regression test covers duplicate matches. **Local execution and live GitHub mutation were not performed during preparation**; consult the branch/PR GitHub Actions results for execution evidence. Existing API pagination and remote race limitations remain.

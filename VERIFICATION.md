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

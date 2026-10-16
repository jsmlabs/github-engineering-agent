# Installation and maintenance

## Supported scope
- Python 3.11+ and Git should already be installed. Python standard library Tk is optional for the graphical maintenance window.
- Install/update/repair from a **trusted local wheel**, supplied with independently verified lowercase SHA-256.
- No registry entries, system service, admin privileges, self-update discovery, hidden download, credential storage, or global PATH modification.
- The application is installed in a dedicated user-data directory containing a virtual environment.

## One-click entry points

- Windows 10/11: double-click `install-windows.cmd` from the extracted repository. It opens the optional Tk maintenance dashboard when Python/Tk are available. Progress is shown while a task runs and closing the window is disabled until the task completes.
- macOS/Linux: run `sh ./install-unix.sh` from the repository root.
- After installation, use `run-agent.cmd` on Windows or `sh ./run-agent.sh` on macOS/Linux to launch the active verified release. These launchers run in the foreground until the agent exits; they no longer stop a healthy GUI/menu session after 240 seconds. Installation and verification subprocesses still have a bounded timeout. Launchers do not download or install Python, Git or release files; supply a trusted local wheel and checksum in the interface.

## Environment readiness

Run `python scripts/setup_check.py --json` to inspect Python compatibility, Git/Docker CLI presence, and GitHub/OpenAI credential **presence only**. No external requests, secret values, permissions or configuration changes occur. The same check is available as **Environment** in the GUI. Choose **Preview** to inspect the selected local wheel, existing installation version, and requested target without changing files or contacting a provider.

## Usage
```bash
python scripts/installer.py preview --wheel /absolute/release.whl --sha256 CHECKSUM
python scripts/installer.py install --wheel /absolute/release.whl --sha256 CHECKSUM
python scripts/installer.py verify
python scripts/installer.py update --wheel /absolute/new-release.whl --sha256 CHECKSUM
python scripts/installer.py repair --wheel /absolute/release.whl --sha256 CHECKSUM
python scripts/installer.py rollback
python scripts/installer.py status
python scripts/installer.py launch --agent-args gui
python scripts/installer.py uninstall --confirm UNINSTALL
python scripts/installer_gui.py
```

For a custom install location, provide `--target /path/under/user/home`. Uninstall refuses any unknown top-level entries. Install/repair also reject symlinked ownership markers and unexpected release-slot entries, preserving unrelated files. It removes the managed virtual environment, so keep personal files elsewhere.

## Offline package verification

From the repository checkout, run `python scripts/verify_package.py` with Python 3.11+ and an already-installed build backend compatible with `pyproject.toml` (`setuptools>=70`). The script disables package-index access, copies the packaging source to a temporary directory, builds one wheel, checks distribution version and console-entry-point metadata, installs it without dependencies into an isolated temporary venv and executes both help commands. The temporary directory is removed on exit. A distinct GitHub Actions package matrix exercises Python 3.11 on Ubuntu, macOS and Windows.

This verifies that the local wheel is installable in the checked environments, not cryptographic publisher identity, trusted artifact distribution, GUI operability or live API integration. No release asset is uploaded by this check.

## Known limitations
- The installer is an **offline preview**, not a completed one-click distribution package.
- The expected hash must come from a trusted channel separate from the wheel; SHA-256 alone does not establish publisher identity. The installer also bounds wheel size (64 MiB), expanded archive content (256 MiB), and archive entry count (5,000), and verifies archive CRCs before invoking pip. Before pip runs, the selected wheel is copied to a private temporary directory and independently re-verified, so concurrent modification of the original path cannot change the artifact pip uses.
- **Repair** explicitly reinstalls the selected wheel only when its digest matches the active release. This may repair missing package files but is not transactional if the current environment is damaged during reinstallation.
- Managed `state.json` reads are limited to 256,000 bytes and reject duplicate JSON keys, nonstandard numeric constants, boolean schema values and missing required fields. Invalid state is never overwritten automatically; inspect and back up the file before manual recovery.
- Each wheel uses its own persistent virtual environment. Activation of a verified release is atomic via a small local state file and the previously active release remains available for rollback. Interrupted installation can leave an incomplete release slot; retry repair with the same wheel/checksum. A local `.installer.lock` serializes mutation operations; if the process terminates abruptly, inspect the installation and confirm no installer process is active before removing that stale lock manually. The installer does not provide transactional rollback of arbitrary external effects.
- There is no automatic release discovery, publisher signature verification, remote update manifest, release notes viewer, shortcut provisioning, or OS-level integration.
- Desktop interaction, Windows installation pathways and actual wheel build/install are not fully exercised by headless tests.
- Do not treat a newer source commit on `main` as a released upgrade.

## Recovery
If verification fails, re-run repair with a known-good wheel and checksum. If the directory is damaged but still contains the managed marker, first back up any files. Remove unknown files yourself only after inspection; the uninstall refuses to delete them automatically. Avoid manipulating application credentials as part of recovery.

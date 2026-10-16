# Installation and maintenance

## Supported scope
- Python 3.11+ and Git should already be installed. Python standard library Tk is optional for the graphical maintenance window.
- Install/update/repair from a **trusted local wheel**, supplied with independently verified lowercase SHA-256.
- No registry entries, system service, admin privileges, self-update discovery, hidden download, credential storage, or global PATH modification.
- The application is installed in a dedicated user-data directory containing a virtual environment.

## One-click entry points

- Windows 10/11: double-click `install-windows.cmd` from the extracted repository. It opens the optional Tk maintenance window when Python/Tk are available.
- macOS/Linux: run `sh ./install-unix.sh` from the repository root.
- Both launchers are frontend entry points only. They do not download or install Python, Git or release files; supply a trusted local wheel and checksum in the interface.

## Usage
```bash
python scripts/installer.py install --wheel /absolute/release.whl --sha256 CHECKSUM
python scripts/installer.py verify
python scripts/installer.py update --wheel /absolute/new-release.whl --sha256 CHECKSUM
python scripts/installer.py repair --wheel /absolute/release.whl --sha256 CHECKSUM
python scripts/installer.py uninstall --confirm UNINSTALL
python scripts/installer_gui.py
```

For a custom install location, provide `--target /path/under/user/home`. Uninstall refuses any unknown top-level entries. It removes the managed virtual environment, so keep personal files elsewhere.

## Known limitations
- The installer is an **offline preview**, not a completed one-click distribution package.
- The expected hash must come from a trusted channel separate from the wheel; SHA-256 alone does not establish publisher identity.
- Install/repair/update use pip against an existing venv, which is not atomic. Failed or interrupted upgrades may leave an unhealthy installation.
- There is no old-version rollback, release discovery, secure update manifest, release notes viewer, shortcuts, or OS-level integration.
- Desktop interaction, Windows installation pathways and actual wheel build/install are not fully exercised by headless tests.
- Do not treat a newer source commit on `main` as a released upgrade.

## Recovery
If verification fails, re-run repair with a known-good wheel and checksum. If the directory is damaged but still contains the managed marker, first back up any files. Remove unknown files yourself only after inspection; the uninstall refuses to delete them automatically. Avoid manipulating application credentials as part of recovery.

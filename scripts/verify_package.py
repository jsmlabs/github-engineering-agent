"""Build and install the project's wheel offline, without network or credentials."""
from __future__ import annotations

from email.parser import Parser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(*argv: str, cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(argv, cwd=cwd, env=env, text=True,
                            capture_output=True, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(f"Package check failed (exit {result.returncode}): {' '.join(argv[:4])}\n"
                           f"{(result.stderr or result.stdout)[-2500:]}")
    return result.stdout.strip()


def main() -> int:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    expected_name, expected_version = project["name"], project["version"]
    env = os.environ.copy()
    env.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_INPUT="1")
    with tempfile.TemporaryDirectory(prefix="gh-engineer-package-") as directory:
        work = Path(directory)
        wheels = work / "wheels"
        wheels.mkdir()
        run(sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
            "--wheel-dir", str(wheels), str(ROOT), cwd=work, env=env)
        artifacts = list(wheels.glob("*.whl"))
        if len(artifacts) != 1:
            raise RuntimeError(f"Expected exactly one wheel, got {len(artifacts)}")
        with zipfile.ZipFile(artifacts[0]) as archive:
            names = archive.namelist()
            metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
            if len(metadata_paths) != 1 or len(names) != len(set(names)):
                raise RuntimeError("Wheel has missing or ambiguous metadata")
            metadata = Parser().parsestr(archive.read(metadata_paths[0]).decode("utf-8"))
            if metadata.get("Name") != expected_name or metadata.get("Version") != expected_version:
                raise RuntimeError("Wheel metadata does not match pyproject.toml")
            entries = metadata_paths[0].removesuffix("METADATA") + "entry_points.txt"
            if entries not in names or "gh-engineer = gh_agent.cli:main" not in archive.read(entries).decode("utf-8"):
                raise RuntimeError("Wheel is missing its advertised CLI entry point")
        environment = work / "isolated"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(str(python), "-m", "pip", "install", "--no-index", "--no-deps",
            str(artifacts[0]), cwd=work, env=env)
        probe = """import json, pathlib, sys, gh_agent
from importlib.metadata import version
print(json.dumps({'version': version('github-engineering-agent'), 'module': str(pathlib.Path(gh_agent.__file__).resolve()), 'prefix': str(pathlib.Path(sys.prefix).resolve())}))"""
        installed = json.loads(run(str(python), "-c", probe, cwd=work, env=env))
        if installed["version"] != expected_version or not Path(installed["module"]).is_relative_to(Path(installed["prefix"])):
            raise RuntimeError("The imported package is not the isolated installed wheel")
        run(str(python), "-m", "gh_agent", "--help", cwd=work, env=env)
        launcher = environment / ("Scripts/gh-engineer.exe" if os.name == "nt" else "bin/gh-engineer")
        run(str(launcher), "--help", cwd=work, env=env)
    print(f"PACKAGE_VERIFICATION_PASS (offline wheel build, install, metadata and CLI: {expected_version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

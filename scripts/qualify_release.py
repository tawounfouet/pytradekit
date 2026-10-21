"""Build and qualify PyTradeKit release artifacts in a clean environment."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest for a file."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _venv_python(environment: Path) -> Path:
    """Return the Python executable inside a virtual environment."""
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"

    return environment / "bin" / "python"


def _build_artifacts(dist_dir: Path) -> tuple[Path, Path]:
    """Build exactly one wheel and one source distribution."""
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(dist_dir)],
        cwd=REPOSITORY_ROOT,
        check=True,
    )

    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))

    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError(
            "Release qualification requires exactly one wheel and one sdist."
        )

    return wheels[0], sdists[0]


def _qualify_clean_install(wheel: Path, environment: Path) -> None:
    """Install the wheel in a clean venv and run public smoke checks."""
    venv.EnvBuilder(with_pip=True).create(environment)
    python = _venv_python(environment)

    subprocess.run(
        [str(python), "-m", "pip", "install", str(wheel)],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    subprocess.run(
        [str(python), "-c", "import pytradekit; print(pytradekit.__version__)"],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    subprocess.run(
        [str(python), "examples/01_foundations.py"],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def main() -> int:
    """Build, hash, clean-install, and smoke-test release artifacts."""
    with tempfile.TemporaryDirectory(prefix="pytradekit-release-") as raw_temp:
        temp_root = Path(raw_temp)
        dist_dir = temp_root / "dist"
        environment = temp_root / "venv"
        dist_dir.mkdir()

        wheel, sdist = _build_artifacts(dist_dir)

        print(f"wheel: {wheel.name}")
        print(f"wheel sha256: {_sha256(wheel)}")
        print(f"sdist: {sdist.name}")
        print(f"sdist sha256: {_sha256(sdist)}")

        _qualify_clean_install(wheel, environment)

    print("Release artifact qualification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

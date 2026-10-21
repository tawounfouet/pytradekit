"""Build and qualify PyTradeKit release artifacts in a clean environment."""

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = (
    Path("examples/01_foundations.py"),
    Path("examples/02_market_order_lifecycle.py"),
    Path("examples/03_uncertain_submission_reconciliation.py"),
    Path("examples/04_cancel_fill_race.py"),
    Path("examples/05_portfolio_risk.py"),
    Path("examples/06_strategy_backtest.py"),
)

RELEASE_DOCUMENTS = (
    Path("docs/architecture/strategy-backtest.md"),
    Path("docs/guides/strategy.md"),
    Path("docs/guides/backtesting.md"),
)


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest for a file."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _project_version() -> str:
    """Read the package version from pyproject.toml."""
    data = tomllib.loads(
        (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    raw_version: object = data["project"]["version"]

    if not isinstance(raw_version, str) or not raw_version:
        raise RuntimeError("Project version must be a non-empty string.")

    return raw_version


def _source_version() -> str:
    """Read __version__ from the package source without importing the package."""
    source_path = REPOSITORY_ROOT / "src" / "pytradekit" / "__init__.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        ):
            continue

        raw_value: object = ast.literal_eval(node.value)
        if isinstance(raw_value, str) and raw_value:
            return raw_value

        raise RuntimeError("Package __version__ must be a non-empty string.")

    raise RuntimeError("Package __version__ assignment was not found.")


def _qualify_release_metadata(expected_version: str) -> None:
    """Validate repository metadata required for a versioned release."""
    source_version = _source_version()
    if source_version != expected_version:
        raise RuntimeError(
            "pyproject.toml and pytradekit.__version__ must declare the same version."
        )

    release_notes = REPOSITORY_ROOT / "docs" / "releases" / f"{expected_version}.md"
    if not release_notes.is_file():
        raise RuntimeError(
            f"Release notes are required at docs/releases/{expected_version}.md."
        )

    lines = release_notes.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith(f"# PyTradeKit {expected_version} - "):
        raise RuntimeError(
            "Release notes must start with '# PyTradeKit <version> - <title>'."
        )

    changelog = (REPOSITORY_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{expected_version}] - " not in changelog:
        raise RuntimeError("CHANGELOG.md does not contain the release version.")

    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    expected_version_block = f"Current release version:\n\n~~~text\n{expected_version}\n~~~"
    if expected_version_block not in readme:
        raise RuntimeError("README.md does not declare the release version.")

    for document in RELEASE_DOCUMENTS:
        if not (REPOSITORY_ROOT / document).is_file():
            raise RuntimeError(f"Release documentation is missing: {document}")

    for example in EXAMPLES:
        if not (REPOSITORY_ROOT / example).is_file():
            raise RuntimeError(f"Release example is missing: {example}")


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


def _qualify_clean_install(
    wheel: Path,
    environment: Path,
    *,
    expected_version: str,
) -> None:
    """Install the wheel in a clean venv and run public smoke checks."""
    venv.EnvBuilder(with_pip=True).create(environment)
    python = _venv_python(environment)

    subprocess.run(
        [str(python), "-m", "pip", "install", str(wheel)],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    subprocess.run(
        [
            str(python),
            "-c",
            (
                "import pytradekit; "
                f"assert pytradekit.__version__ == {expected_version!r}; "
                "print(pytradekit.__version__)"
            ),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
    )

    for example in EXAMPLES:
        subprocess.run(
            [str(python), str(example)],
            cwd=REPOSITORY_ROOT,
            check=True,
        )


def main() -> int:
    """Validate metadata, build, hash, clean-install, and smoke-test artifacts."""
    expected_version = _project_version()
    _qualify_release_metadata(expected_version)

    with tempfile.TemporaryDirectory(prefix="pytradekit-release-") as raw_temp:
        temp_root = Path(raw_temp)
        dist_dir = temp_root / "dist"
        environment = temp_root / "venv"
        dist_dir.mkdir()

        wheel, sdist = _build_artifacts(dist_dir)

        print(f"version: {expected_version}")
        print(f"wheel: {wheel.name}")
        print(f"wheel sha256: {_sha256(wheel)}")
        print(f"sdist: {sdist.name}")
        print(f"sdist sha256: {_sha256(sdist)}")

        _qualify_clean_install(
            wheel,
            environment,
            expected_version=expected_version,
        )

    print("Release artifact qualification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

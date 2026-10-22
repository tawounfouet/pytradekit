"""Static qualification for the single-node PAPER deployment profile."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    """Validate deployment files without resolving secret values."""

    required = (
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
        ".env.example",
        "alembic.ini",
        "scripts/container_entrypoint.sh",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(
            "Deployment qualification files are missing: " + ", ".join(missing)
        )

    dockerfile = _text("Dockerfile")
    compose = _text("docker-compose.yml")
    alembic = _text("alembic.ini")
    entrypoint = _text("scripts/container_entrypoint.sh")

    if "USER pytradekit" not in dockerfile or "/health/live" not in dockerfile:
        raise RuntimeError("Dockerfile is missing LOT-07 hardening controls.")
    if "pytradekit-entrypoint" not in dockerfile:
        raise RuntimeError("Dockerfile must use the migration entrypoint.")

    forbidden_compose = (
        "POSTGRES_PASSWORD:",
        "PYTRADEKIT_ALPACA_PAPER_API_KEY:",
        "PYTRADEKIT_ALPACA_PAPER_SECRET_KEY:",
    )
    if any(marker in compose for marker in forbidden_compose):
        raise RuntimeError("Compose contains a raw secret configuration key.")
    if "file:///run/secrets/" not in compose:
        raise RuntimeError("Compose does not use file-backed secret references.")
    if "read_only: true" not in compose or "no-new-privileges:true" not in compose:
        raise RuntimeError("Compose is missing container hardening controls.")

    if "postgresql+psycopg://" in alembic:
        raise RuntimeError("alembic.ini must not persist a database URL.")

    migration_pos = entrypoint.find("alembic -c /app/alembic.ini upgrade head")
    runtime_pos = entrypoint.find('exec pytradekit "$@"')
    if migration_pos < 0 or runtime_pos < 0 or migration_pos > runtime_pos:
        raise RuntimeError("Container must run migrations before runtime startup.")

    print("Single-node deployment qualification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

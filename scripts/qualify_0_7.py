"""Static release-blocker qualification for PyTradeKit 0.7."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_TESTS = (
    "tests/e2e/test_security_authorization.py",
    "tests/e2e/test_safety_gate.py",
    "tests/e2e/test_safety_governance.py",
    "tests/e2e/test_operational_health.py",
    "tests/e2e/test_operations_observability.py",
    "tests/e2e/test_secret_provider_outage.py",
    "tests/qualification/security_operations/test_authorization_blockers.py",
    "tests/qualification/security_operations/test_safety_blockers.py",
    "tests/integration/test_security_operations_production_qualification.py",
)

REQUIRED_RUNBOOKS = (
    "docs/runbooks/AUTHORIZATION_DENIED.md",
    "docs/runbooks/KILL_SWITCH_ACTIVATION.md",
    "docs/runbooks/KILL_SWITCH_RELEASE.md",
    "docs/runbooks/RISK_OVERRIDE.md",
    "docs/runbooks/CRITICAL_MISMATCH.md",
    "docs/runbooks/TRADING_READINESS_LOST.md",
    "docs/runbooks/DATABASE_UNAVAILABLE.md",
    "docs/runbooks/BROKER_DISCONNECTED.md",
    "docs/runbooks/ALERT_DELIVERY_FAILURE.md",
    "docs/runbooks/SECRET_PROVIDER_UNAVAILABLE.md",
    "docs/runbooks/SECRET_ROTATION.md",
    "docs/runbooks/STARTUP_TIMEOUT.md",
    "docs/runbooks/PYTRADEKIT_0_7_RELEASE_QUALIFICATION.md",
)


def _require(paths: tuple[str, ...], label: str) -> None:
    missing = [path for path in paths if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(f"Missing {label}: " + ", ".join(missing))


def main() -> int:
    """Verify release evidence and the hard LIVE prohibition."""

    _require(REQUIRED_TESTS, "qualification tests")
    _require(REQUIRED_RUNBOOKS, "runbooks")

    configuration = (
        ROOT / "src/pytradekit/runtime/configuration.py"
    ).read_text(encoding="utf-8")
    alpaca_runtime = (
        ROOT / "src/pytradekit/brokers/adapters/alpaca/runtime.py"
    ).read_text(encoding="utf-8")
    deployment = (
        ROOT / "src/pytradekit/runtime/deployment_security.py"
    ).read_text(encoding="utf-8")

    if 'LIVE = "LIVE"' in configuration:
        raise RuntimeError("0.7 must not expose a LIVE runtime environment.")
    if "RuntimeEnvironment.LIVE" in alpaca_runtime:
        raise RuntimeError("Alpaca runtime must remain PAPER-only in 0.7.")
    if "paper=True" not in alpaca_runtime:
        raise RuntimeError("Alpaca command composition must force PAPER mode.")
    if "https://api.alpaca.markets" in deployment:
        raise RuntimeError("LIVE Alpaca trading endpoint must remain unavailable.")

    report = ROOT / "docs/qualification/0.7-production-qualification.md"
    if not report.is_file():
        raise RuntimeError("0.7 production qualification report is missing.")

    print("PyTradeKit 0.7 production qualification evidence passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

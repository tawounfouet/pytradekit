# PyTradeKit

PyTradeKit is a **domain-first, broker-agnostic trading framework** designed around explicit domain semantics, deterministic behavior, recoverability, testability, and progressive broker qualification.

## Current milestone

**PyTradeKit 0.1.x — Domain Foundations**

The 0.1 milestone establishes the canonical financial language and architectural foundations required by the future OMS, Portfolio/Risk, Backtest, and Broker Integration milestones.

> PyTradeKit 0.1 provides domain foundations only. It does not yet connect to brokers or execute trades.

## Architecture

PyTradeKit follows:

- Domain-Driven Design
- Hexagonal Architecture
- Ports & Adapters
- Modular Monolith
- Vertical-slice delivery

The initial core is intentionally infrastructure-free: **no database, no broker SDK, no network dependency, and no web framework**.

## Requirements

- Python 3.12+

## Development setup

```bash
git clone https://github.com/tawounfouet/pytradekit.git
cd pytradekit

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

make check
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Version

```bash
pytradekit --version
```

Bootstrap version:

```text
0.1.0a1
```

## Package topology

```text
src/pytradekit/
├── shared/
├── reference/
│   └── domain/
├── runtime/
│   ├── ports/
│   └── adapters/
└── testing/
    ├── builders/
    └── strategies/
```

The folders are intentionally skeletal in the bootstrap commit. Domain implementations are added incrementally during milestone 0.1.

## Critical path

```text
0.1 Foundations
→ 0.2 OMS & Execution
→ 0.3 Portfolio & Risk
→ 0.4 Strategy & Backtest
→ 0.5 Persistence + Alpaca Paper
→ 0.6 Reconciliation & Recovery
→ 0.7 Security & Operations
→ 0.8 Broker Compliance + IBKR
→ 0.9 Release Hardening
→ 1.0 Stable MVP
```

## License

A project license will be selected explicitly before the first public release.

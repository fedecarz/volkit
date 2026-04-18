# volkit

A Python library for volatility analytics — pricing, IV surfaces, and variance risk premium analysis.

## The Strategy

Options are systematically overpriced relative to realized volatility. This gap, the **Variance Risk Premium**, is the signal:

    VRP = IV − RV

When VRP > 0, options are expensive. volkit identifies when the spread is large enough to trade.

## Modules

| Module | Purpose |
|--------|---------|
| **market_data** | Fetch options chains and price history from multiple providers |
| **black_scholes** | Black-Scholes pricer and Greeks from scratch |
| **iv_surface** | IV surface builder using Newton-Raphson solver |
| **vol_spread** | Implied vs realized vol spread analyzer |

## Pipeline

    market_data  →  black_scholes  →  iv_surface  →  vol_spread
    Fetch data       Price options     Build surface   VRP signal

## Quickstart

```python
from volkit import market_data
from volkit.iv_surface import plot_surface
from volkit.vol_spread import analyze_vol_spread

snapshot = market_data.get_market_snapshot(
    "SPY",
    expiry_from="2026-05-01",
    expiry_to="2026-12-31"
)

plot_surface(snapshot["options"], spot=snapshot["spot"], title="SPY IV Surface")

analyze_vol_spread(
    price_history=snapshot["price_history"],
    options=snapshot["options"],
    spot=snapshot["spot"],
    ticker="SPY",
    mode="vix_adjusted",
)
```

## IV Surface

Built using the OTM convention and Newton-Raphson inversion of Black-Scholes across all strikes and expiries. Shows volatility skew, term structure, and mispricings.

<!-- ![SPY IV Surface](assets/spy_iv_surface.png) -->

## Vol Spread

Compares implied vol to rolling realized vol to identify rich/cheap regimes. Uses VIX as historical IV proxy with a basis adjustment:

    basis          = our_IV_today - VIX_today
    IV_adjusted(t) = VIX(t) + basis
    spread(t)      = IV_adjusted(t) - RV(t)

Three modes: `vix_adjusted` (recommended), `vix_raw` (historical analysis), `scalar` (flat IV).

<!-- ![SPY Vol Spread](assets/spy_vol_spread.png) -->

## Data Providers

| Provider | Price History | Options Chain | API Key |
|----------|--------------|---------------|---------|
| Yahoo Finance | ✓ | ✓ | Not required |
| Massive | ✓ | Paid plan | Required |
| MarketData.app | ✓ | ✓ | Required (free tier) |

## Installation

```bash
git clone https://github.com/fedecarz/volkit.git
cd volkit
pip install -e .
```

## Requirements

Python 3.8+ · numpy · scipy · pandas · plotly · yfinance · matplotlib · massive · requests · python-dotenv

## License

MIT

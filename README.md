# volkit

A Python library for volatility analytics.

## Modules

- **market_data** — fetch and clean options chains and price history
  - Supports multiple providers: Yahoo Finance (no key), Massive, MarketData.app
- **black_scholes** — Black-Scholes pricer and Greeks implemented from scratch
- **iv_surface** — implied volatility surface builder using Newton-Raphson solver
- **vol_spread** — implied vs realized volatility spread analyzer

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

- Python 3.8+
- numpy, scipy, pandas, yfinance, plotly, matplotlib, massive, requests, python-dotenv

## Status

Work in progress — modules being added progressively.

## License

MIT

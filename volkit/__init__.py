"""
volkit — volatility analytics library.
Options pricing, IV surface, and vol spread analysis.
"""

__version__ = "0.1.0"

from volkit import market_data
from volkit.black_scholes import bs_price, greeks
from volkit.iv_surface import plot_surface, build_iv_surface, implied_volatility
from volkit.vol_spread import analyze_vol_spread, realized_vol, atm_implied_vol, compute_vol_spread

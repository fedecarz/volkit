"""
volkit.market_data
------------------
Market data layer — fetch options chains and price history.
Supports multiple data providers: yahoo, massive, marketdata
"""

from volkit.market_data.providers.yahoo import YahooProvider
from volkit.market_data.providers.massive_provider import MassiveProvider
from volkit.market_data.providers.marketdata_provider import MarketDataProvider


def _get_provider(provider: str, api_key: str = None):
    if provider == "yahoo":
        return YahooProvider()              # no API key needed
    elif provider == "massive":
        if api_key is None:
            raise ValueError("Massive requires an api_key.")
        return MassiveProvider(api_key)
    elif provider == "marketdata":
        if api_key is None:
            raise ValueError("MarketData requires an api_key.")
        return MarketDataProvider(api_key)
    else:
        raise ValueError(f"Unknown provider '{provider}'. Choose 'yahoo', 'massive', or 'marketdata'.")


def get_price_history(ticker, period="1y", interval="1d", start=None, end=None, provider="yahoo", api_key=None):
    """
    Fetch OHLCV price history for a ticker.
    Examples:
    get_price_history("SPY")                                                            # 1 year, Yahoo
    get_price_history("SPY", start="2020-01-01", end="2023-01-01")                      # date range
    get_price_history("SPY", provider="massive", api_key="...")                         # via Massive
    """
    return _get_provider(provider, api_key).get_price_history(ticker, period, interval, start, end)


def get_options_chain(ticker, expiry=None, date=None, expiry_from=None, expiry_to=None, provider="yahoo", api_key=None):
    """
    Fetch options chain for a ticker.
    Examples
    get_options_chain("SPY")                                                            # all expiries, Yahoo
    get_options_chain("SPY", expiry="2026-05-15")                                       # specific expiry
    get_options_chain("SPY", expiry_from="2026-05-01", expiry_to="2026-12-31")          # date range
    get_options_chain("SPY", date="2025-01-17", provider="marketdata", api_key="...")   # historical
    """
    return _get_provider(provider, api_key).get_options_chain(ticker, expiry, date, expiry_from, expiry_to)


def get_market_snapshot(ticker, expiry_from=None, expiry_to=None, start=None, end=None, provider="yahoo", api_key=None):
    """
    Fetch everything at once — price history, spot price, and options chain.
    Examples
    get_market_snapshot("SPY")                                                          # full snapshot, Yahoo
    get_market_snapshot("SPY", expiry_from="2026-05-01", expiry_to="2026-09-30")        # filtered expiries
    get_market_snapshot("SPY", start="2022-01-01")                                      # custom price history range
    """
    return _get_provider(provider, api_key).get_market_snapshot(ticker, expiry_from, expiry_to, start, end)

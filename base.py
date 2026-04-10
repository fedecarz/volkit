"""
volkit.market_data.base
-----------------------
Abstract base class that every data provider must implement.
"""

from abc import ABC, abstractmethod     # ABC = Abstract Base Class, abstractmethod = decorator that forces subclasses to implement the method
import pandas as pd


class MarketDataProvider(ABC):          # inheriting from ABC makes this class abstract — it cannot be instantiated directly
    """
    Contract that every data provider must follow. Any class that inherits from this must implement all three methods below.
    """
    @abstractmethod     # this decorator marks the method as required — subclasses must implement it
    def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d", start: str = None, end: str = None) -> pd.DataFrame:
        """Return cleaned OHLCV price history."""
        pass

    @abstractmethod
    def get_options_chain(self, ticker: str, expiry: str = None, date: str = None, expiry_from: str = None, expiry_to: str = None) -> pd.DataFrame:
        """Return cleaned options chain."""
        pass

    @abstractmethod
    def get_market_snapshot(self, ticker: str, expiry_from: str = None, expiry_to: str = None, start: str = None, end: str = None) -> dict:
        """Return spot price, price history, and options chain in one call."""
        pass



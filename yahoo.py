"""
volkit.market_data.providers.yahoo
---------------------------------
Yahoo finance data provider, API key is not required.
Uses the yfinance library to fetch price history and options chains
"""

import pandas as pd
import yfinance as yf
from volkit.market_data.base import MarketDataProvider

class YahooProvider(MarketDataProvider):
    
    # Get price history ------------------------------------
    
    def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d", start: str = None, end: str = None) -> pd.DataFrame:
        """
        Fetch OHLCV price history from yahoo finance
        Params
        ticker   : "SPY", "AMZN" ...
        period   : "1mo", "3mo", "6mo", "1y", "2y" — ignored if start is set
        interval : "1d", "1wk" ...
        start    : "2020-01-01" — if set, overrides period
        end      : "2026-01-01" — optional, defaults to today
        """
        if start is not None:
            # if start date is provided, use date range instead of period
            raw = yf.Ticker(ticker).history(start=start, end=end, interval=interval)
        else:
            # default — use period lookback window
            raw = yf.Ticker(ticker).history(period=period, interval=interval)

        if raw.empty:
            raise ValueError(f"No price data returned for '{ticker}'. Check the ticker symbol.")
        
        return self.clean_price_history(raw)
    
    
    def clean_price_history(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean raw yfinance price history data
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]        # lowercase all column names for consistency

        # keep only OHLCV columns
        cols = []
        for c in ["open", "high", "low", "close", "volume"]:
            if c in df.columns:
                cols.append(c)
        df = df[cols]

        df = df.dropna(subset=["close"])                    # drop rows where close is NaN
        df = df[~df.index.duplicated(keep="first")]         # remove duplicate timestamps

        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)           # strip timezone
        
        df.sort_index(inplace=True)

        return df
    
        
    # Get options chains ------------------------------------

    def get_options_chain(self, ticker: str, expiry: str = None, date: str = None, expiry_from: str = None, expiry_to: str = None) -> pd.DataFrame:
        """
        Fetch option chains data from yahoo finance
        Params
        ticker      : "SPY", "AMZN" ...
        expiry      : specific expiry as "YYYY-MM-DD", or None to fetch all
        expiry_from : filter options expiring after this date
        expiry_to   : filter options expiring before this date
        """
        tk = yf.Ticker(ticker)
        available = tk.options                              # tuple of available expiry date strings

        if not available:
            raise ValueError(f"No options data found for {ticker}")
        
        if expiry is not None:
            if expiry not in available:
                raise ValueError(f"Expiry {expiry} not available, choose from: {list(available)}")
            expiries_to_fetch = [expiry]
        else:
            expiries_to_fetch = list(available)             # fetch all available expiries
        
        frames = []
        for exp in expiries_to_fetch:
            chain = tk.option_chain(exp)                    # returns a named tuple with .calls and .puts

            calls = chain.calls.copy()
            calls["option_type"] = "call" 

            puts = chain.puts.copy()
            puts["option_type"] = "put"

            combined = pd.concat([calls, puts], ignore_index=True)
            combined["expiry"] = exp                        # add expiry column — not included by yfinance 
            frames.append(combined)

        raw = pd.concat(frames, ignore_index=True)          # combine all expiries into one DataFrame
        df = self.clean_options_chain(raw)

        # filter by expiry range
        if expiry_from is not None:
            df = df[df["expiry"] >= expiry_from]            # string comparison works because format is YYYY-MM-DD
        if expiry_to is not None:
            df = df[df["expiry"] <= expiry_to]

        return df
    
    
    def clean_options_chain(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean raw yfinance options data.
        """
        df = df.copy()

        # rename yfinance columns to consistent names used across all providers
        rename = {
            "strike":            "strike",
            "bid":               "bid",
            "ask":               "ask",
            "lastPrice":         "last",
            "openInterest":      "open_interest",
            "volume":            "volume",
            "impliedVolatility": "implied_volatility",
            "option_type":       "option_type",
            "expiry":            "expiry"
        }
        df = df.rename(columns=rename)      

        # keep only the renamed columns
        cols = []
        for c in rename.values():
            if c in df.columns:
                cols.append(c)
        df = df[cols]

        # coerce to numeric — yfinance can return mixed types
        df["last"] = pd.to_numeric(df["last"], errors="coerce").fillna(0)
        df["bid"]  = pd.to_numeric(df["bid"],  errors="coerce").fillna(0)
        df["ask"]  = pd.to_numeric(df["ask"],  errors="coerce").fillna(0)

        # mid price — when market is open use (bid+ask)/2, when closed use last price as fallback
        df["mid"] = df.apply(
            lambda row: row["last"] if (row["bid"] == 0 and row["ask"] == 0 and row["last"] > 0)
            else (row["bid"] + row["ask"]) / 2,
            axis=1
        )

        # filters
        df = df[df["mid"] > 0]                      # drop rows with no usable price
        df = df[df["bid"] <= df["ask"]]             # drop data errors where bid > ask
        df = df[df["open_interest"] >= 5]          # drop illiquid strikes — price is unreliable below this threshold
        df = df[df["strike"] > 0]                   # drop bad strikes — zero strike would cause division by zero in Black-Scholes
        df = df.reset_index(drop=True)

        return df
    

    # Get market snapshot ------------------------------------

    def get_market_snapshot(self, ticker: str, expiry_from: str = None, expiry_to: str = None, start: str = None, end: str = None) -> dict:
        """
        Fetch price history, spot price and full options chain in one call
        Returns a dict with: ticker, spot, price_history, options, expiries
        """
        price_history = self.get_price_history(ticker, start=start, end=end)
        spot = float(price_history["close"].iloc[-1])
        options = self.get_options_chain(ticker, expiry_from=expiry_from, expiry_to=expiry_to)
        expiries = sorted(options["expiry"].unique().tolist())              # sorted list of unique expiry dates

        print(f"  Spot price    : ${spot:.2f}")
        print(f"  Price bars    : {len(price_history)}")
        print(f"  Options rows  : {len(options)}")
        print(f"  Expiries      : {len(expiries)}")

        return {
            "ticker":        ticker,
            "spot":          spot,
            "price_history": price_history,
            "options":       options,
            "expiries":      expiries,
        }
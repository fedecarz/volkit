"""
volkit.market_data.providers.marketdata_provider
-------------------------------------------------
MarketData.app data provider.
Requires a free API key from marketdata.app
Provides: price history and full options chain with bid, ask, IV, Greeks.
"""

import requests
import pandas as pd
from volkit.market_data.base import MarketDataProvider as BaseProvider          # renamed to avoid clash with this class name


BASE_URL = "https://api.marketdata.app/v1"


class MarketDataProvider(BaseProvider):

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",                               # Bearer token — standard auth header for REST APIs
        }

    # Price History ---------------------------------------

    def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d", start: str = None, end: str = None) -> pd.DataFrame:
        """
        Fetch OHLCV price history from MarketData.app.
        Params
        ticker   : "SPY", "AMZN" ...
        period   : "1mo", "3mo", "6mo", "1y", "2y" — ignored if start is set
        interval : "1d" only for now
        start    : "2020-01-01" — if set, overrides period
        end      : "2026-01-01" — optional, defaults to today
        """
        from datetime import date, timedelta

        period_map = {
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y":  365,
            "2y":  730,
        }

        if start is not None:
            from_date = start
            to_date   = end if end is not None else date.today().strftime("%Y-%m-%d")
        else:
            days      = period_map.get(period, 365)
            from_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
            to_date   = date.today().strftime("%Y-%m-%d")

        url = f"{BASE_URL}/stocks/candles/D/{ticker}/"          # D = daily candles
        params = {
            "from": from_date,
            "to":   to_date,
        }

        response = requests.get(url, headers=self.headers, params=params)
        data     = response.json()

        if data.get("s") != "ok":                               # MarketData uses "s" field for status — "ok" means success
            raise ValueError(f"MarketData error for '{ticker}': {data.get('errmsg', data.get('message', 'unknown error'))}")

        # MarketData returns columnar format, each field is an array -> data["c"] = [close1, close2, ...], data["t"] = [timestamp1, timestamp2, ...]
        df = pd.DataFrame({
            "open":   data["o"],
            "high":   data["h"],
            "low":    data["l"],
            "close":  data["c"],
            "volume": data["v"],
        }, index=pd.to_datetime(data["t"], unit="s"))       # timestamps are in seconds

        df.index.name = "date"

        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        else:
            df.index = df.index.normalize()                 # keep date only

        df = df.sort_index()
        return df

    # Options Chain ---------------------------------------

    def get_options_chain(self, ticker: str, expiry: str = None, date: str = None, expiry_from: str = None, expiry_to: str = None) -> pd.DataFrame:
        """
        Fetch options chain from MarketData.app.

        Parameters
        ----------
        ticker      : e.g. "SPY"
        expiry      : specific expiry as "YYYY-MM-DD", or None for all
        date        : historical date as "YYYY-MM-DD", or None for today
        expiry_from : filter options expiring after this date
        expiry_to   : filter options expiring before this date

        Note: fetching expiration=all on large tickers like SPY costs many credits.
        """
        url    = f"{BASE_URL}/options/chain/{ticker}/"
        params = {}

        if expiry is not None:
            params["expiration"] = expiry
        else:
            params["expiration"] = "all"                    # fetch all expiries — expensive on large tickers (usage limit easy to reach)

        if date is not None:
            params["date"] = date                           # historical snapshot — returns chain as of that date

        response = requests.get(url, headers=self.headers, params=params)
        data     = response.json()

        if data.get("s") == "no_data":                      # no_data means the expiry exists but has no quotes
            print(f"\n  Warning: '{ticker}' expiry '{expiry}' has no data available — skipping")
            return pd.DataFrame()                           # return empty DataFrame so caller can handle

        if data.get("s") != "ok":
            raise ValueError(f"MarketData error for '{ticker}': {data.get('errmsg', data.get('message', 'unknown error'))}")

        # MarketData returns columnar arrays — same pattern as price history
        df = pd.DataFrame({
            "option_symbol":      data["optionSymbol"],
            "strike":             data["strike"],
            "expiry":             pd.to_datetime(data["expiration"], unit="s").strftime("%Y-%m-%d"),        # convert Unix timestamp to date string
            "option_type":        data["side"],
            "bid":                data["bid"],
            "ask":                data["ask"],
            "mid":                data["mid"],              # MarketData mid — keep it for convenience
            "last":               data["last"],
            "volume":             data["volume"],
            "open_interest":      data["openInterest"],
            "implied_volatility": data["iv"],                # MarketData IV — useful to cross-check the solver
            "delta":              data["delta"],
            "gamma":              data["gamma"],
            "theta":              data["theta"],
            "vega":               data["vega"],
            "dte":                data["dte"],              # days to expiry — pre-calculated by MarketData
            "in_the_money":       data["inTheMoney"],
            "underlying_price":   data["underlyingPrice"],
        })

        # coerce numeric columns — historical data often has None values
        df["bid"]                = pd.to_numeric(df["bid"],                errors="coerce").fillna(0)       # fill NaN
        df["ask"]                = pd.to_numeric(df["ask"],                errors="coerce").fillna(0)       # fill NaN
        df["open_interest"]      = pd.to_numeric(df["open_interest"],      errors="coerce").fillna(0)       # fill NaN
        df["implied_volatility"] = pd.to_numeric(df["implied_volatility"], errors="coerce")                 # keep NaN — we compute our IV

        # filters
        df = df[df["bid"] <= df["ask"]]             # drop data errors
        df = df[df["open_interest"] >= 10]          # drop illiquid strikes
        df = df[df["strike"] > 0]                   # drop bad strikes
        df = df.reset_index(drop=True)              # resets index values

        # filter by expiry range
        if expiry_from is not None:
            df = df[df["expiry"] >= expiry_from]
        if expiry_to is not None:
            df = df[df["expiry"] <= expiry_to]

        # summary
        expiries_loaded = sorted(df["expiry"].unique().tolist())
        print(f"\n  Options chain loaded for {ticker}:")
        print(f"  Expiries : {expiries_loaded}")
        print(f"  Rows     : {len(df)}")
        
        return df

    # Market Snapshot --------------------------------------

    def get_market_snapshot(self, ticker: str, expiry_from: str = None, expiry_to: str = None, start: str = None, end: str = None) -> dict:
        """
        Fetch price history, spot price and full options chain in one call.
        Returns a dict with: ticker, spot, price_history, options, expiries
        """

        price_history = self.get_price_history(ticker, start=start, end=end)
        spot          = float(price_history["close"].iloc[-1])
        options       = self.get_options_chain(ticker, expiry_from=expiry_from, expiry_to=expiry_to)
        expiries      = sorted(options["expiry"].unique().tolist())

        # get all available expiries to compare against what was loaded
        all_available = sorted(set(
            pd.to_datetime(
                requests.get(
                    f"{BASE_URL}/options/chain/{ticker}/",
                    headers=self.headers,
                    params={"expiration": "all"}
                ).json().get("expiration", []),
                unit="s"
            ).strftime("%Y-%m-%d")
        ))

        # filter available by range if specified
        if expiry_from is not None:
            all_available = [e for e in all_available if e >= expiry_from]
        if expiry_to is not None:
            all_available = [e for e in all_available if e <= expiry_to]

        skipped = [e for e in all_available if e not in expiries]

        print(f"  Spot price    : ${spot:.2f}")
        print(f"  Price bars    : {len(price_history)}")
        print(f"  Options rows  : {len(options)}")
        print(f"  Expiries loaded     : {expiries}")

        if skipped:
            print(f" Expiries skipped: {skipped} - no data available")

        return {
            "ticker":        ticker,
            "spot":          spot,
            "price_history": price_history,
            "options":       options,
            "expiries":      expiries,
        }

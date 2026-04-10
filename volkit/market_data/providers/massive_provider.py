"""
volkit.market_data.providers.massive
---------------------------------------
Massive (formerly Polygon.io) data provider.
Requires an API key from massive.com
"""

import pandas as pd
from massive import RESTClient
from volkit.market_data.base import MarketDataProvider


class MassiveProvider(MarketDataProvider):

    def __init__(self, api_key: str):
        self.client = RESTClient(api_key=api_key)               # create the Massive client once and reuse it across all method calls

    # Price History ----------------------------------

    def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d", start: str = None, end: str = None) -> pd.DataFrame:
        """
        Fetch OHLCV price history from Massive.
        Params
        ticker   : "SPY", "AMZN" ...
        period   : "1mo", "3mo", "6mo", "1y", "2y" — ignored if start is set
        interval : "1d", "1wk" ...
        start    : "2020-01-01" — if set, overrides period
        end      : "2026-01-01" — optional, defaults to today
        """
        from datetime import date, timedelta

        # map period strings to number of days
        period_map = {
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y":  365,
            "2y":  730,
        }

        if start is not None:
            # use explicit date range
            from_date = start
            to_date   = end if end is not None else date.today().strftime("%Y-%m-%d")       # default end is today
        else:
            # calculate date range from period
            days      = period_map.get(period, 365)                                         # default to 1y if period not recognized
            to_date   = date.today().strftime("%Y-%m-%d")
            from_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

        aggs = []
        for a in self.client.list_aggs(
            ticker=ticker,
            multiplier=1,                       # 1 day per bar
            timespan="day",
            from_=from_date,
            to=to_date,
            limit=50000,                        # max bars per request — 50000
        ):
            aggs.append(a)                      # list_aggs is a generator — we collect all results

        if not aggs:
            raise ValueError(f"No price data returned for {ticker}.")

        df = pd.DataFrame([{                    # build DataFrame from the list of aggregate objects
            "open":   a.open,
            "high":   a.high,
            "low":    a.low,
            "close":  a.close,
            "volume": a.volume,
            "date":   pd.to_datetime(a.timestamp, unit="ms"),               # Massive returns Unix timestamps in milliseconds
        } for a in aggs])

        df = df.set_index("date")
        df = df.sort_index()

        if df.index.tz is not None:                                         # strip timezone for consistency
            df.index = df.index.tz_localize(None)
        else:
            df.index = df.index.normalize()                                 # keep date only

        return df


    # Options chain ----------------------------------

    def get_options_chain(self, ticker: str, expiry: str = None, date: str = None, expiry_from: str = None, expiry_to: str = None) -> pd.DataFrame:
        """
        Fetch options chain from Massive.
        Params
        ticker      : "SPY", "AMZN" ...
        expiry      : specific expiry as "YYYY-MM-DD", or None to fetch all
        expiry_from : filter options expiring after this date
        expiry_to   : filter options expiring before this date
        """
        params = {}
        if expiry is not None:
            params["expiration_date"] = expiry                              # filter by expiry on the API side — saves bandwidth

        rows = []
        for o in self.client.list_snapshot_options_chain(ticker, params=params):
            details = o.details
            day     = o.day                                                 # day aggregate — volume, close price

            rows.append({
                "strike":             details.strike_price,
                "expiry":             details.expiration_date,
                "option_type":        details.contract_type,
                "bid":                o.last_quote.bid if o.last_quote else None,           # last_quote can be None for illiquid options
                "ask":                o.last_quote.ask if o.last_quote else None,
                "last":               day.close        if day else None,
                "volume":             day.volume       if day else None,
                "open_interest":      o.open_interest,
                "implied_volatility": o.implied_volatility,
            })

        if not rows:
            raise ValueError(f"No options data found for {ticker}")

        df = pd.DataFrame(rows)

        # coerce to numeric — API can return None for some fields
        df["last"] = pd.to_numeric(df["last"], errors="coerce").fillna(0)
        df["bid"]  = pd.to_numeric(df["bid"],  errors="coerce").fillna(0)
        df["ask"]  = pd.to_numeric(df["ask"],  errors="coerce").fillna(0)

        # mid price — fallback to last when market is closed
        df["mid"] = df.apply(
            lambda row: row["last"] if (row["bid"] == 0 and row["ask"] == 0 and row["last"] > 0)
            else (row["bid"] + row["ask"]) / 2,
            axis=1
        )

        # filters
        df = df[df["mid"] > 0]
        df = df[df["bid"] <= df["ask"]]
        df = df[df["open_interest"] >= 10]
        df = df[df["strike"] > 0]
        df = df.reset_index(drop=True)

        # filter by expiry range
        if expiry_from is not None:
            df = df[df["expiry"] >= expiry_from]
        if expiry_to is not None:
            df = df[df["expiry"] <= expiry_to]

        return df


    # Market snapshot ----------------------------------

    def get_market_snapshot(self, ticker: str, expiry_from: str = None, expiry_to: str = None, start: str = None, end: str = None) -> dict:
        """
        Fetch price history, spot price and full options chain in one call.
        Returns a dict with: ticker, spot, price_history, options, expiries
        """

        price_history = self.get_price_history(ticker, start=start, end=end)
        spot          = float(price_history["close"].iloc[-1])
        options       = self.get_options_chain(ticker, expiry_from=expiry_from, expiry_to=expiry_to)
        expiries      = sorted(options["expiry"].unique().tolist())

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

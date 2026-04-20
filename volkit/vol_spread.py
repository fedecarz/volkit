"""
volkit.vol_spread
--------------------------
Implied vs realized volatility spread analyzer.
Computes rolling realized volatility from price history, compares it to implied volatility from the options chains and plots the spread over time to identify rich/cheap vol regimes.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# Realized volatility ------------------------

def realized_vol(price_history: pd.DataFrame, window: int = 21, trading_days: int = 252) -> pd.Series:
    """
    Compute rolling realized volatility from daily close prices. Uses log returns annualized.
    Params:
    price_history: Dataframe with a "close" column and DatetimeIndex
    window: rolling window in trading days (default is 21 = 1 month)
    trading_days: number of trading days per year (default is 252)
    """

    log_returns = np.log(price_history["close"] / price_history["close"].shift(1))
    rv = log_returns.rolling(window=window).std() * np.sqrt(trading_days)
    rv.name = "realized_vol"
    return rv

# ATM implied volatility ------------------------

def atm_implied_vol(options: pd.DataFrame, spot: float, expiry: str = None, use_solver: bool = True) -> float:
    """
    Extract the at-the-money implied volatility from the options chain. Finds the strike closest to spot and returns its IV. Uses the average of call and put IV at that strike.
    Params
    options : cleaned options DataFrame from market_data
    spot    : current spot price
    expiry  : specific expiry to use, or None to use nearest expiry
    use_solver : if True, compute IV using Newton-Raphson solver
                 if False, use implied_volatility column from the data provider
    """

    from volkit.utils import get_risk_free_rate
    r = get_risk_free_rate()
    
    if expiry is not None:
        df = options[options["expiry"] == expiry].copy()
    else:       # Use nearest expiry
        expiries = sorted(options["expiry"].unique())
        df = options[options["expiry"] == expiries[0]].copy()
        expiry = expiries[0]    # needed for using the IV solver
    
    if df.empty:
        return np.nan
    
    # Find strike closest to spot
    df["distance"] = abs(df["strike"] - spot)
    atm_strike = df.loc[df["distance"].idxmin(), "strike"]
    atm_options = df[df["strike"] == atm_strike]

    if use_solver:
        from volkit.iv_surface import implied_volatility as iv_solver
        T = (datetime.strptime(expiry, "%Y-%m-%d") - datetime.today()).days / 365
        
        if T<=0:
            return np.nan
        
        row_call = atm_options[atm_options["option_type"] == "call"]
        row_put  = atm_options[atm_options["option_type"] == "put"]
        iv_call = np.nan
        iv_put  = np.nan

        if not row_call.empty:
            iv_call = iv_solver(row_call.iloc[0]["mid"], spot, atm_strike, T, r, "call")
        if not row_put.empty:
            iv_put = iv_solver(row_put.iloc[0]["mid"], spot, atm_strike, T, r, "put")

        # average call and put if both available, otherwise use whichever converged
        values = [v for v in [iv_call, iv_put] if not np.isnan(v)]
        return float(np.mean(values)) if values else np.nan
    else:
        # use implied_volatility column from provider — faster, no solver needed
        iv_values = atm_options["implied_volatility"].dropna()
        if iv_values.empty:
            return np.nan
        return float(iv_values.mean())

# Vol spread -----------------------------------------------------

"""
we need a daily historical IV series. The ideal approach would be to run the IV solver on historical options chain data, computing ATM IV for each past trading day.
However, Yahoo Finance does not provide historical options chains and other providers limit api calls. We cannot directly reconstruct a daily IV time series from Yahoo data. 
-> use VIX as a proxy for historical IV.

Basis Adjustment
the solver computes ATM IV from specific data that will differ from VIX due to:
- Different underlying (SPY vs SPX)
- Different strike selection and expiry
- Different interpolation

we measure the difference (basis) today and apply it as a correction to the historical VIX series: the result is a historically consistent IV series that reflects the solver's calibration.
The spread IV_adjusted(t) - RV(t) is then a more precise estimate of the variance risk premium over time.
"""

def compute_vol_spread(price_history: pd.DataFrame, options: pd.DataFrame, spot: float, iv: float = None, window: int = 21, mode: str = "vix_adjusted", expiry: str = None,  use_solver: bool = True) -> pd.DataFrame:
    """
    Compute the vol spread (IV - realized vol) over time -> time series of the variance risk premium (VRP).
    Params:
    price_history : DataFrame with 'close' column and DatetimeIndex
    options       : cleaned options DataFrame — used to compute today's ATM IV
    spot          : current spot price — used to find ATM strike
    iv            : pre-computed IV scalar (optional) — if None, computed from options
    window        : rolling window for realized vol (default 21 days)
    mode          : IV method to use. Options:
                        "vix_adjusted" — VIX history corrected by today's basis (recommended)
                        "vix_raw"      — raw VIX history with no adjustment
                        "scalar"       — single IV value as flat line
    expiry        : specific expiry for ATM IV extraction, or None for nearest
    use_solver : if True, compute IV using Newton-Raphson solver
                 if False, use implied_volatility column from the data provider
    """

    import yfinance as yf

    rv = realized_vol(price_history, window=window)

    if mode in ("vix_adjusted", "vix_raw"):
        # fetch VIX history aligned to price_history date range
        start = price_history.index[0].strftime("%Y-%m-%d")
        end = price_history.index[-1].strftime("%Y-%m-%d")
        vix = yf.Ticker("^VIX").history(start=start, end=end)["Close"] / 100  # VIX is in % —> convert to decimal

        # strip timezone if present
        if vix.index.tz is not None:
            vix.index = vix.index.tz_localize(None)
        else:
            vix.index = vix.index.normalize()
        
        # align VIX to price_history dates — forward fill any missing days
        vix = vix.reindex(price_history.index, method="ffill")

        if mode == "vix_adjusted":
            # compute our ATM IV today using the solver
            iv_today = iv if iv is not None else atm_implied_vol(options, spot, expiry, use_solver=use_solver)

            if np.isnan(iv_today):
                raise ValueError(
                    "Could not compute ATM implied volatility from options chain. "
                    "Check that the options DataFrame is not empty and contains implied_volatility values."
                )
        
            # compute basis — systematic difference between our solver and VIX
            vix_today = vix.iloc[-1]
            basis = iv_today - vix_today 

            print(f"  VIX today         : {vix_today*100:.1f}%")
            print(f"  Our ATM IV today  : {iv_today*100:.1f}%")
            print(f"  Basis             : {basis*100:+.1f}%")

            # apply basis correction to historical VIX series
            iv_series = vix + basis

        else: # vix_raw
            iv_series = vix

    elif mode == "scalar":
        # single IV value applied to all dates
        iv_today  = iv if iv is not None else atm_implied_vol(options, spot, expiry, use_solver=use_solver)
        iv_series = iv_today
    else:
        raise ValueError(f"Unknown mode '{mode}'. Choose one of: 'vix_adjusted', 'vix_raw', 'scalar'.")

    df = pd.DataFrame({
        "close"         : price_history["close"],
        "realized_vol"  : rv,
        "implied_vol"   : iv_series,
        "spread"        : iv_series - rv    # positive = vol rich (IV > RV), negative = vol cheap
    })

    df = df.dropna()

    return df


# Plot the vol spread -----------------------------

def plot_vol_spread(spread_df: pd.DataFrame, ticker: str = "", window: float = 21, rich_threshold: float = 0.02):
    """
    Plot implied vol, realized vol, and the spread between them.
    Highlights regions where vol is rich (spread > threshold) and cheap (spread < -threshold).
    Params:
    spread_df       : DataFrame from compute_vol_spread
    ticker          : ticker symbol for the plot title
    window          : rolling window used (for labeling)
    rich_threshold  : spread threshold to flag rich/cheap regimes (default 2%)
    """
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14,10), sharex=True)      # two stacked panels sharing x axis
    fig.suptitle(f"{ticker} Implied vs Realized Volatility ({window}d window)", fontsize=14)

    # top panel: IV and RV over timee
    ax1.plot(spread_df.index, spread_df["implied_vol"]*100, label="Implied Vol", color="#E8593C", linewidth=1.5)
    ax1.plot(spread_df.index, spread_df["realized_vol"]*100, label=f"Realized Vol ({window}d)", color="#1D9E75", linewidth=1.5)

    # shade the area between IV and RV — red when IV > RV (rich), green when IV < RV (cheap)
    ax1.fill_between(
        spread_df.index,
        spread_df["implied_vol"] * 100,
        spread_df["realized_vol"] * 100,
        where=spread_df["implied_vol"] >= spread_df["realized_vol"],
        alpha=0.15, color="#E8593C", label="Vol rich (sell signal)"
    )
    ax1.fill_between(
        spread_df.index,
        spread_df["implied_vol"] * 100,
        spread_df["realized_vol"] * 100,
        where=spread_df["implied_vol"] < spread_df["realized_vol"],
        alpha=0.15, color="#1D9E75", label="Vol cheap (buy signal)"
    )

    ax1.set_ylabel("Volatility (%)")
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))

    # bottom panel: spread (IV - RV) over time
    spread_pct = spread_df["spread"] * 100

    ax2.plot(spread_df.index, spread_pct,
             color="#3B8BD4", linewidth=1.5, label="Vol spread (IV - RV)")
    ax2.axhline(0, color="black", linewidth=0.8, linestyle="--")                   # zero line

    # threshold lines — signal when spread is large enough to trade
    ax2.axhline(rich_threshold * 100, color="#E8593C",
                linewidth=0.8, linestyle=":", label=f"Rich threshold (+{rich_threshold*100:.0f}%)")
    ax2.axhline(-rich_threshold * 100, color="#1D9E75",
                linewidth=0.8, linestyle=":", label=f"Cheap threshold (-{rich_threshold*100:.0f}%)")

    # shade positive spread red, negative spread green
    ax2.fill_between(spread_df.index, spread_pct, 0,
                     where=spread_pct >= 0, alpha=0.2, color="#E8593C")
    ax2.fill_between(spread_df.index, spread_pct, 0,
                     where=spread_pct < 0, alpha=0.2, color="#1D9E75")
    
    ax2.set_ylabel("Spread (%)")
    ax2.set_xlabel("Date")
    ax2.legend(loc="upper left", fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))                   # format dates as "Jan 2025"
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))                   # tick every 2 months

    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


# Convenience ----------------------

def analyze_vol_spread(price_history: pd.DataFrame, options: pd.DataFrame, spot: float, ticker: str = "", window: int = 21, expiry: str = None, mode: str = "vix_adjusted", rich_threshold: float = 0.02,  use_solver: bool = True):
    """
    Full vol spread analysis in one call. Computes ATM IV, rolling realized vol, the spread, prints a summary, and plots everything.
    Params
    price_history   : DataFrame with 'close' column
    options         : cleaned options DataFrame
    spot            : current spot price
    ticker          : ticker symbol for labels
    window          : rolling window for realized vol
    expiry          : specific expiry for IV, or None for nearest
    mode            : IV method to use. Options:
                        "vix_adjusted" — VIX history corrected by today's basis (recommended)
                        "vix_raw"      — raw VIX history with no adjustment
                        "scalar"       — single IV value as flat line
    rich_threshold  : spread threshold to flag regimes
    use_solver : if True, compute IV using Newton-Raphson solver
                 if False, use implied_volatility column from the data provider
    """
    # extract ATM IV from the options chain
    iv = atm_implied_vol(options, spot, expiry, use_solver=use_solver)

    if np.isnan(iv):
        raise ValueError("Could not compute ATM implied volatility. Check options chain.")

    spread_df = compute_vol_spread(price_history, options, spot, iv, window, mode, expiry, use_solver=use_solver)

    # summary statistics
    current_rv     = spread_df["realized_vol"].iloc[-1]
    current_spread = spread_df["spread"].iloc[-1]
    pct_time_rich  = (spread_df["spread"] > 0).mean() * 100   # % of time IV > RV historically

    print(f"-"*60)
    print(f"{ticker} Vol Spread Analysis")
    print(f"  Realized Vol ({window}d) : {current_rv*100:.1f}%")
    print(f"  Current Spread    : {current_spread*100:+.1f}%")
    print(f"  Vol rich          : {pct_time_rich:.0f}% of the time")
    print(f"  Regime            : {'RICH — vol expensive, consider selling' if current_spread > rich_threshold else 'CHEAP — vol underpriced, consider buying' if current_spread < -rich_threshold else 'NEUTRAL'}")

    plot_vol_spread(spread_df, ticker=ticker, window=window, rich_threshold=rich_threshold)

    return spread_df

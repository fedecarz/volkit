"""
volkit.iv_surface
-----------------
Implied volatility solver and surface builder.

Takes real market option prices, backs out implied volatility using Newton-Raphson iteration, and plots the IV surface across strikes and maturities.

Functions:
- implied_volatility
- build_iv_surface
- plot-surface
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import cm
from datetime import datetime
from volkit.black_scholes import bs_price, vega


# IV Solver ----------------------------------------------------------

def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> float:
    """
    Compute implied volatility using Newton-Raphson iteration. Solves for sigma such that BS_price(sigma) == market_price.

    Params
    market_price   : observed market price (use mid price)
    S              : spot price
    K              : strike price
    T              : time to expiry in years
    r              : risk-free rate
    option_type    : "call" or "put"
    max_iterations : maximum Newton-Raphson iterations
    tolerance      : convergence threshold
    """
    if T <= 0:
        return np.nan

    # intrinsic value check — market price must exceed intrinsic value
    if option_type == "call":
        intrinsic = max(S - K, 0)
    else:
        intrinsic = max(K - S, 0)

    if market_price <= intrinsic:
        return np.nan

    # initial guess — use time value only for better ITM convergence
    time_value = max(market_price - intrinsic, 1e-6)
    sigma = np.sqrt(2 * np.pi / T) * (time_value / S)
    sigma = np.clip(sigma, 1e-4, 10.0)

    for i in range(max_iterations):
        price = bs_price(S, K, T, r, sigma, option_type)
        v = vega(S, K, T, r, sigma) * 100  # vega is divided by 100 in bs module

        if abs(v) < 1e-10:
            return np.nan

        diff  = price - market_price
        sigma = sigma - diff / v

        sigma = np.clip(sigma, 1e-4, 10.0)

        if abs(diff) < tolerance:
            return sigma

    return np.nan


# Surface Builder --------------------------------------------------------------

def build_iv_surface(
    options: pd.DataFrame,
    spot: float,
    r: float = 0.05,
    as_of_date: str = None,
) -> pd.DataFrame:
    """
    Compute implied volatility for every option using OTM convention. Uses puts for strikes below spot, calls for strikes above spot.

    Params
    options     : cleaned options DataFrame from market_data
    spot        : current spot price
    r           : risk-free rate
    as_of_date  : historical date as "YYYY-MM-DD", or None for today
    """
    today = datetime.strptime(as_of_date, "%Y-%m-%d") if as_of_date else datetime.today()

    # OTM convention — puts below spot, calls above spot
    calls = options[(options["option_type"] == "call") & (options["strike"] >= spot)].copy()
    puts  = options[(options["option_type"] == "put")  & (options["strike"] <  spot)].copy()
    df    = pd.concat([calls, puts], ignore_index=True)

    # dynamic strike range — 70% to 130% of spot
    lower = spot * 0.70
    upper = spot * 1.30
    df = df[(df["strike"] >= lower) & (df["strike"] <= upper)]
    df["_type"] = df["option_type"]

    # compute T — time to expiry in years
    df["T"] = df["expiry"].apply(
        lambda e: max((datetime.strptime(e, "%Y-%m-%d") - today).days / 365, 1e-6)
    )

    # compute IV for each row
    df["iv"] = df.apply(
        lambda row: implied_volatility(
            market_price=row["mid"],
            S=spot,
            K=row["strike"],
            T=row["T"],
            r=r,
            option_type=row["_type"],
        ),
        axis=1,
    )

    # drop rows where solver failed
    df = df.dropna(subset=["iv"])

    # filter extreme IVs — anything above 500% is probably a data error
    df = df[df["iv"] < 5.0]
    df = df[df["iv"] > 0.01]

    return df[["strike", "expiry", "T", "mid", "iv"]].reset_index(drop=True)


# Surface Plot -------------------------------------------------------------

def plot_surface(
    options: pd.DataFrame,
    spot: float,
    r: float = 0.05,
    title: str = "Implied Volatility Surface",
    as_of_date: str = None,
):
    """
    Build and plot the implied volatility surface using matplotlib.
    Opens in a separate window.
    """
    surface_df = build_iv_surface(options, spot, r, as_of_date)

    if surface_df.empty:
        raise ValueError("No valid IV data to plot. Check your options chain.")
    if len(surface_df["expiry"].unique())<2:
        raise ValueError(f"Not enough expiries to build a surface — only {len(surface_df['expiry'].unique())} found. Try fetching more expiries.")


    pivot = surface_df.pivot_table(
        index="T",
        columns="strike",
        values="iv",
        aggfunc="mean",
    )
    
    # interpolate missing strikes across each expiry row
    pivot = pivot.interpolate(axis=1, limit_direction="both")
    # interpolate missing expiries across each strike column
    pivot = pivot.interpolate(axis=0, limit_direction="both")

    strikes    = pivot.columns.values.astype(float)
    maturities = pivot.index.values.astype(float)
    iv_matrix  = pivot.values * 100  # convert to percentage

    S, T = np.meshgrid(strikes, maturities)

    fig = plt.figure(figsize=(12, 7))
    ax  = fig.add_subplot(111, projection="3d")
    ax.view_init(elev=20, azim=-45)

    surf = ax.plot_surface(S, T, iv_matrix, cmap=cm.RdYlBu_r, edgecolor="none", alpha=0.9)

    fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, label="IV %")

    ax.set_xlabel("Strike")
    ax.set_ylabel("Time to Expiry (years)")
    ax.set_zlabel("Implied Vol (%)")
    ax.set_title(title)

    plt.tight_layout()
    plt.show()
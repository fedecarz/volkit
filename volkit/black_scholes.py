"""
volkit.black_scholes
--------------------
Black-Scholes option pricer and Greeks. Supports European calls and puts.

Inputs
S     : spot price
K     : strike price
T     : time to expiry in years (30 days = 30/365)
r     : risk-free rate (0.05 for 5%)
sigma : volatility (0.2 for 20%)

Functions:
- _d1
- _d2
- bs_price
- delta
- gamma
- vega
- theta
- rho
- greeks
"""

import numpy as np
from scipy.stats import norm


def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Computes d1, the standardized distance from spot to strike, adjusted for drift and volatility.
    """
    return (np.log(S/K) + (r+0.5*sigma**2)*T) / (sigma*np.sqrt(T))

def _d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Computes d2, represents the risk-neutral probability of expiring in the money.
    """
    return _d1(S,K,T,r,sigma) - sigma * np.sqrt(T)

def bs_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> float:
    """
    Black-Scholes price for a European call or put
    """

    if T <= 0:      # Option expired -> intrinsic value only
        if option_type == "call":
            return max(S-K,0)
        else:
            return max(K-S,0)
        
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)

    if option_type == "call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    elif option_type == "put":
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    else:
        raise ValueError(f"option_type must be 'call' or 'put', got '{option_type}'")
    

# Greeks ----------------------------------------

def delta(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> float:
    """
    Delta — sensitivity of option price to a $1 move in spot.
    Delta of a call: between 0 and 1.
    Delta of a put: between -1 and 0.
    """
    if T <= 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0

    d1 = _d1(S, K, T, r, sigma)

    if option_type == "call":
        return norm.cdf(d1)
    elif option_type == "put":
        return norm.cdf(d1) - 1
    else:
        raise ValueError(f"option_type must be 'call' or 'put', got '{option_type}'")


def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Gamma — rate of change of delta per $1 move in spot.
    Peaks at ATM and decays away from the money.
    """
    if T <= 0:
        return 0.0

    d1 = _d1(S, K, T, r, sigma)
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Vega — sensitivity of option price to a 1 point move in volatility.
    Divided by 100 to express per 1% move in vol.
    """
    if T <= 0:
        return 0.0

    d1 = _d1(S, K, T, r, sigma)
    return S * norm.pdf(d1) * np.sqrt(T) / 100


def theta(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> float:
    """
    Theta — daily time decay of the option price.
    Always negative for long options.
    Divided by 365 to express as daily decay.
    """
    if T <= 0:
        return 0.0

    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)

    decay = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))

    if option_type == "call":
        return (decay - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
    elif option_type == "put":
        return (decay + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
    else:
        raise ValueError(f"option_type must be 'call' or 'put', got '{option_type}'")


def rho(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> float:
    """
    Rho — sensitivity of option price to a 1% move in the risk-free rate.
    Divided by 100 to express per 1% move in rates.
    """
    if T <= 0:
        return 0.0

    d2 = _d2(S, K, T, r, sigma)

    if option_type == "call":
        return K * T * np.exp(-r * T) * norm.cdf(d2) / 100
    elif option_type == "put":
        return -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
    else:
        raise ValueError(f"option_type must be 'call' or 'put', got '{option_type}'")


def greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> dict:
    """
    Compute all Greeks in one call.
    Returns a dict with keys: delta, gamma, vega, theta, rho
    """
    return {
        "delta": delta(S, K, T, r, sigma, option_type),
        "gamma": gamma(S, K, T, r, sigma),
        "vega":  vega(S, K, T, r, sigma),
        "theta": theta(S, K, T, r, sigma, option_type),
        "rho":   rho(S, K, T, r, sigma, option_type),
    }

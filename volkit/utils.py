"""
volkit.utils
------------
Shared utility functions across volkit modules.
"""

def get_risk_free_rate():
    """
    Fetch current risk-free rate from US 3-month Treasury bill yield.
    Uses ^IRX ticker from Yahoo Finance.
    Returns annualized rate as decimal.
    """
    import yfinance as yf
    irx = yf.Ticker("^IRX").history(period="5d")["Close"]
    if irx.empty:
        return 0.04     # Value if data is unavailable
    return float(irx.iloc[-1])/100      # IRX is in % so it is converted to decimal
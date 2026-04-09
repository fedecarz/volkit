from setuptools import setup, find_packages

setup(
    name="volkit",
    version="0.1.0",
    description="Volatility analytics library — Black-Scholes, IV surface, vol spread",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.24.0",
        "scipy>=1.11.0",
        "pandas>=2.0.0",
        "yfinance>=0.2.0",
        "plotly>=5.0.0",
        "matplotlib>=3.7.0",
        "massive>=1.0.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
    ],
)
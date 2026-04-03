"""
DataProvider implementation backed by the yfinance library.
"""

import pandas as pd
from .base import DataProvider


class YFinanceProvider(DataProvider):

    def __init__(self) -> None:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise ImportError("yfinance is required for YFinanceProvider: pip install yfinance") from exc
        self._yf = yf
        self._cache: dict = {}

    def _ticker(self, symbol: str):
        if symbol not in self._cache:
            self._cache[symbol] = self._yf.Ticker(symbol)
        return self._cache[symbol]

    def get_spot(self, ticker: str) -> float:
        t = self._ticker(ticker)
        try:
            return float(t.fast_info["lastPrice"])
        except Exception:
            history = t.history(period="1d")
            if history.empty:
                raise ValueError(f"Could not retrieve price for {ticker!r}")
            return float(history["Close"].iloc[-1])

    def get_expirations(self, ticker: str) -> list[str]:
        return list(self._ticker(ticker).options)

    def get_option_chain(self, ticker: str, expiration: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        chain = self._ticker(ticker).option_chain(expiration)
        return chain.calls[["strike", "bid", "ask"]].copy(), chain.puts[["strike", "bid", "ask"]].copy()

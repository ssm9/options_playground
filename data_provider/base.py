"""
Abstract base class for options data providers.
Implement this to plug in any data source (e.g. Tradier, Polygon, CBOE, IBKR).
"""

from abc import ABC, abstractmethod
import pandas as pd


class DataProvider(ABC):

    @abstractmethod
    def get_spot(self, ticker: str) -> float:
        """Return the current spot price for *ticker*."""

    @abstractmethod
    def get_expirations(self, ticker: str) -> list[str]:
        """
        Return a sorted list of expiration date strings in 'YYYY-MM-DD' format
        for all available options on *ticker*.
        """

    @abstractmethod
    def get_option_chain(self, ticker: str, expiration: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Return (calls, puts) DataFrames for *ticker* at *expiration*.
        Each DataFrame must contain at least the columns: strike, bid, ask.
        """

"""
DataProvider implementation backed by the Tradier brokerage API.

Requires a Tradier account and API token:
  https://developer.tradier.com/getting_started

Set sandbox=True to use the free paper-trading sandbox (delayed data).
Set sandbox=False for a live brokerage account (real-time data).
"""

import requests
import pandas as pd
from .base import DataProvider


class TradierProvider(DataProvider):
    _PRODUCTION_URL = "https://api.tradier.com/v1"
    _SANDBOX_URL = "https://sandbox.tradier.com/v1"

    def __init__(self, api_token: str, sandbox: bool = False) -> None:
        self._base = self._SANDBOX_URL if sandbox else self._PRODUCTION_URL
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
        })

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = self._session.get(f"{self._base}{path}", params=params or {})
        r.raise_for_status()
        return r.json()

    def get_spot(self, ticker: str) -> float:
        data = self._get("/markets/quotes", {"symbols": ticker})
        return float(data["quotes"]["quote"]["last"])

    def get_expirations(self, ticker: str) -> list[str]:
        data = self._get("/markets/options/expirations", {"symbol": ticker})
        dates = data["expirations"]["date"]
        # API returns a string when there is only one expiration
        if isinstance(dates, str):
            dates = [dates]
        return sorted(dates)

    def get_option_chain(self, ticker: str, expiration: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        data = self._get("/markets/options/chains", {
            "symbol": ticker,
            "expiration": expiration,
            "greeks": "false",
        })
        options = data["options"]["option"]
        # API returns a dict (not a list) when there is only one contract
        if isinstance(options, dict):
            options = [options]

        df = pd.DataFrame(options)[["option_type", "strike", "bid", "ask"]]
        df["strike"] = df["strike"].astype(float)
        df["bid"] = pd.to_numeric(df["bid"], errors="coerce").fillna(0.0)
        df["ask"] = pd.to_numeric(df["ask"], errors="coerce").fillna(0.0)

        calls = df[df["option_type"] == "call"][["strike", "bid", "ask"]].reset_index(drop=True)
        puts  = df[df["option_type"] == "put"][["strike", "bid", "ask"]].reset_index(drop=True)
        return calls, puts

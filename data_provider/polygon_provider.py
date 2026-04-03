"""
DataProvider implementation backed by the Polygon.io API.

Requires a Polygon.io API key:
  https://polygon.io/dashboard/signup

The free tier provides delayed quotes (15 min). A paid "Starter" plan or
above provides real-time options data.

Note on pagination: Polygon paginates large option chains via a `next_url`
field in the response. This provider follows all pages automatically.
"""

import requests
import pandas as pd
from .base import DataProvider


class PolygonProvider(DataProvider):
    _BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: str) -> None:
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {api_key}"})

    def _get(self, url: str, params: dict | None = None) -> dict:
        """GET a full URL (pagination hands back complete next_url values)."""
        r = self._session.get(url, params=params or {})
        r.raise_for_status()
        return r.json()

    def _get_all(self, path: str, params: dict | None = None) -> list:
        """Follow Polygon pagination, collecting all results."""
        results = []
        url = f"{self._BASE_URL}{path}"
        while url:
            data = self._get(url, params)
            results.extend(data.get("results", []))
            # next_url is a fully-qualified URL with cursor baked in
            url = data.get("next_url")
            params = None  # subsequent requests must not repeat initial params
        return results

    def get_spot(self, ticker: str) -> float:
        data = self._get(
            f"{self._BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
        )
        return float(data["ticker"]["lastTrade"]["p"])

    def get_expirations(self, ticker: str) -> list[str]:
        # Reference endpoint returns all non-expired contracts; we extract
        # unique expiration dates from it (much cheaper than the snapshot).
        contracts = self._get_all(
            "/v3/reference/options/contracts",
            {"underlying_ticker": ticker, "expired": "false", "limit": 1000},
        )
        dates = sorted({c["expiration_date"] for c in contracts})
        return dates

    def get_option_chain(self, ticker: str, expiration: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Snapshot endpoint returns live bid/ask alongside contract details.
        results = self._get_all(
            f"/v3/snapshot/options/{ticker}",
            {"expiration_date": expiration, "limit": 250},
        )

        rows = []
        for r in results:
            details = r.get("details", {})
            quote   = r.get("last_quote", {})
            rows.append({
                "option_type": details.get("contract_type", ""),
                "strike":      float(details.get("strike_price", 0)),
                "bid":         float(quote.get("bid") or 0),
                "ask":         float(quote.get("ask") or 0),
            })

        if not rows:
            empty = pd.DataFrame(columns=["strike", "bid", "ask"])
            return empty, empty.copy()

        df    = pd.DataFrame(rows)
        calls = df[df["option_type"] == "call"][["strike", "bid", "ask"]].reset_index(drop=True)
        puts  = df[df["option_type"] == "put"][["strike", "bid", "ask"]].reset_index(drop=True)
        return calls, puts

"""
Options screener: finds deep ITM strikes where the near-term ask < far-term bid
across two consecutive expirations.

Data is sourced via a DataProvider. The default implementation uses yfinance;
swap it out by passing any object that satisfies the DataProvider interface.
"""

import sys
from datetime import datetime, timedelta
import pandas as pd

from data_provider import DataProvider, YFinanceProvider


def find_deep_itm_opportunities(
    ticker_symbol: str,
    itm_pct: float = 0.15,
    provider: DataProvider | None = None,
) -> pd.DataFrame:
    """
    Scans all consecutive expiration pairs for deep ITM options where
    near_term_ask < far_term_bid at the same strike.

    Args:
        ticker_symbol: e.g. "SPY", "AAPL"
        itm_pct:       minimum fraction the option must be in-the-money to
                       qualify as "deep ITM". Default 0.15 = 15% ITM.
        provider:      DataProvider instance to use. Defaults to YFinanceProvider.

    Returns:
        DataFrame sorted by (far_bid - near_ask) descending.
    """
    if provider is None:
        provider = YFinanceProvider()

    spot = provider.get_spot(ticker_symbol)

    cutoff = datetime.now() + timedelta(days=30)
    expirations = [
        e for e in provider.get_expirations(ticker_symbol)
        if datetime.strptime(e, "%Y-%m-%d") <= cutoff
    ]
    if len(expirations) < 2:
        print(f"Fewer than 2 expirations available for {ticker_symbol}")
        return pd.DataFrame()

    print(f"{ticker_symbol} spot: ${spot:.2f} | checking {len(expirations) - 1} expiration pairs...\n")

    results = []

    for i in range(len(expirations) - 1):
        exp_near = expirations[i]
        exp_far = expirations[i + 1]

        try:
            calls_near, puts_near = provider.get_option_chain(ticker_symbol, exp_near)
            calls_far, puts_far = provider.get_option_chain(ticker_symbol, exp_far)
        except Exception as e:
            print(f"  Skipping {exp_near}/{exp_far}: {e}")
            continue

        chains = {
            "call": (calls_near, calls_far),
            "put":  (puts_near,  puts_far),
        }

        for option_type, (near_df, far_df) in chains.items():
            # Deep ITM filter:
            #   calls: strike is well below spot  → strike <= spot * (1 - itm_pct)
            #   puts:  strike is well above spot  → strike >= spot * (1 + itm_pct)
            if option_type == "call":
                deep_itm_mask = near_df["strike"] <= spot * (1 - itm_pct)
            else:
                deep_itm_mask = near_df["strike"] >= spot * (1 + itm_pct)

            near_deep = near_df[deep_itm_mask]
            if near_deep.empty:
                continue

            # Merge on strike to find common strikes across both expirations
            merged = near_deep.merge(far_df, on="strike", suffixes=("_near", "_far"))

            # Require valid (non-zero) quotes on both sides
            merged = merged[(merged["ask_near"] > 0) & (merged["bid_far"] > 0)]

            # Core condition: near ask < far bid
            hits = merged[merged["ask_near"] < merged["bid_far"]].copy()
            if hits.empty:
                continue

            hits["type"] = option_type
            hits["exp_near"] = exp_near
            hits["exp_far"] = exp_far
            hits["credit"] = hits["bid_far"] - hits["ask_near"]
            hits["spot"] = spot

            results.append(hits[["type", "strike", "exp_near", "exp_far",
                                  "ask_near", "bid_far", "credit", "spot"]])

    if not results:
        return pd.DataFrame()

    out = pd.concat(results, ignore_index=True)
    return out.sort_values("credit", ascending=False).reset_index(drop=True)


def main():
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "SPY"
    itm_pct = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15

    try:
        results = find_deep_itm_opportunities(ticker, itm_pct=itm_pct)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if results.empty:
        print("No opportunities found.")
        return

    pd.set_option("display.float_format", "{:.2f}".format)
    pd.set_option("display.max_rows", 50)
    print(f"Deep ITM opportunities for {ticker} (ITM threshold: {itm_pct:.0%}):\n")
    print(results.to_string(index=True))
    print(f"\n{len(results)} result(s) found.")


if __name__ == "__main__":
    main()

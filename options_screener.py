"""
Options screener: finds deep ITM strikes where the near-term ask < far-term bid
across two consecutive expirations.
"""

import sys
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd


def find_deep_itm_opportunities(ticker_symbol: str, itm_pct: float = 0.15) -> pd.DataFrame:
    """
    Scans all consecutive expiration pairs for deep ITM options where
    near_term_ask < far_term_bid at the same strike.

    Args:
        ticker_symbol: e.g. "SPY", "AAPL"
        itm_pct: minimum fraction the option must be in-the-money to qualify
                 as "deep ITM". Default 0.15 = 15% ITM.

    Returns:
        DataFrame sorted by (far_bid - near_ask) descending.
    """
    ticker = yf.Ticker(ticker_symbol)

    try:
        spot = ticker.fast_info["lastPrice"]
    except Exception:
        price_info = ticker.history(period="1d")
        if price_info.empty:
            raise ValueError(f"Could not retrieve price for {ticker_symbol!r}")
        spot = float(price_info["Close"].iloc[-1])

    cutoff = datetime.now() + timedelta(days=30)
    expirations = [e for e in ticker.options if datetime.strptime(e, "%Y-%m-%d") <= cutoff]
    if len(expirations) < 2:
        print(f"Fewer than 2 expirations available for {ticker_symbol}")
        return pd.DataFrame()

    print(f"{ticker_symbol} spot: ${spot:.2f} | checking {len(expirations) - 1} expiration pairs...\n")

    results = []

    for i in range(len(expirations) - 1):
        exp_near = expirations[i]
        exp_far = expirations[i + 1]

        try:
            chain_near = ticker.option_chain(exp_near)
            chain_far = ticker.option_chain(exp_far)
        except Exception as e:
            print(f"  Skipping {exp_near}/{exp_far}: {e}")
            continue

        for option_type in ("call", "put"):
            near_df = chain_near.calls if option_type == "call" else chain_near.puts
            far_df = chain_far.calls if option_type == "call" else chain_far.puts

            near_df = near_df[["strike", "bid", "ask"]].copy()
            far_df = far_df[["strike", "bid", "ask"]].copy()

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

            # Merge on strike to find common strikes between the two expirations
            merged = near_deep.merge(far_df, on="strike", suffixes=("_near", "_far"))

            # Require valid (non-zero) quotes on both sides
            merged = merged[
                (merged["ask_near"] > 0) &
                (merged["bid_far"] > 0)
            ]

            # Core condition: near ask < far bid
            hits = merged[merged["ask_near"] < merged["bid_far"]].copy()
            if hits.empty:
                continue

            hits["type"] = option_type
            hits["exp_near"] = exp_near
            hits["exp_far"] = exp_far
            hits["credit"] = hits["bid_far"] - hits["ask_near"]  # net credit if traded
            hits["spot"] = spot

            results.append(hits[["type", "strike", "exp_near", "exp_far",
                                  "ask_near", "bid_far", "credit", "spot"]])

    if not results:
        return pd.DataFrame()

    out = pd.concat(results, ignore_index=True)
    out = out.sort_values("credit", ascending=False).reset_index(drop=True)
    return out


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

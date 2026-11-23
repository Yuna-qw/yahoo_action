"""Validate downloaded CSV coverage and latest monthly dates."""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


MARKETS = ("Shanghai_Shenzhen", "Snp500_Ru1000", "TSX")


def previous_month_end(today=None):
    today = today or date.today()
    return date(today.year, today.month, 1) - timedelta(days=1)


def main():
    expected_date = previous_month_end()
    issues = []
    rows = []

    for market in MARKETS:
        master = pd.read_excel("master_full.xlsx", sheet_name=market, dtype=object)
        tickers = master.loc[
            master["currently use"].astype(str).str.lower().eq("yes"),
            "Yahoo_adj_Ticker_symbol",
        ].dropna().astype(str)
        for ticker in tickers:
            path = Path("new_csv") / market / f"{ticker}.csv"
            status, latest = "ok", ""
            if not path.exists():
                status = "missing"
            else:
                try:
                    data = pd.read_csv(path)
                    if data.empty or data.shape[1] < 2:
                        status = "empty_or_invalid"
                    else:
                        date_col = "Date" if "Date" in data.columns else data.columns[0]
                        latest_date = pd.to_datetime(data[date_col], errors="coerce").dropna().max()
                        if pd.isna(latest_date):
                            status = "invalid_date"
                        else:
                            latest = latest_date.date().isoformat()
                            if latest_date.date() != expected_date:
                                status = "outdated"
                except Exception as exc:
                    status = f"read_error: {exc}"
            rows.append({"market": market, "ticker": ticker, "status": status, "latest_date": latest})
            if status != "ok":
                issues.append(f"{market}/{ticker}: {status} (latest={latest or 'n/a'})")

    report = pd.DataFrame(rows)
    report.to_csv("check_report.csv", index=False)
    print(f"Checked {len(rows)} tickers; expected latest date: {expected_date}; issues: {len(issues)}")
    for issue in issues[:100]:
        print(issue)
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

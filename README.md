# Yahoo data downloader

This directory keeps the original downloader filename and download logic. `run_download.py` reads `settings.json` and calls `1.yahoo_data_download.py` for all markets (`data_option=0`).

Run `python run_download.py` whenever you want to start a full download. This is manual only; there is no configured run date or automatic schedule.

The original script reads `master_symbol_v1.6_2023.03.xlsx` from this directory and writes CSV files to the configured `new_data_dir` (currently `/data/yahoo/new_csv`). Failures remain in `failed_txt/` under this code directory.

`settings.json` also records `old_data_dir` (`/data/yahoo/csv`) for the historical data baseline. The current one-command launcher only downloads; QC/check integration can use that path once its exact data layout is confirmed. The downloader parameters are `use_threads`, `sleep_time`, `repeat`, and `download_method`.

Install dependencies with `python -m pip install -r requirements.txt`.

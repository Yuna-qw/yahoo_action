# Yahoo Actions downloader

This folder contains a GitHub Actions ready version of the project's Yahoo Finance downloader. `master_full.xlsx` is the full master workbook, and the downloader selects stocks marked `currently use = yes` from these markets:

- `Shanghai_Shenzhen`
- `Snp500_Ru1000`
- `TSX`

The GitHub Actions workflow is manual only. Choose **Actions → Yahoo monthly download → Run workflow** to download all master-list stocks marked `currently use = yes`. It then runs `check_download.py`, which checks CSV coverage, readability, and the latest month-end date. Downloaded CSV files and `check_report.csv` are stored as an artifact; they are not committed back to the repository. The original `qc.py` compares against historical CSV data, so it requires a baseline `csv/` dataset that is not included in this test repository.

## Run locally

```bash
python -m pip install -r requirements.txt
python download.py
```

The `qc.py`, `check.py`, and their small helper modules are included from the project's QC flow. These legacy QC scripts expect additional historical QC report spreadsheets and are not part of the scheduled download workflow.

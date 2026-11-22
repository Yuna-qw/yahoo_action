# Yahoo Actions downloader

This folder contains a GitHub Actions ready version of the project's monthly Yahoo Finance downloader. The bundled master workbook is a test fixture containing the first 10 rows marked `currently use = yes` from each market in the original master workbook:

- `Shanghai_Shenzhen`
- `Snp500_Ru1000`
- `TSX`

The workflow checks daily at 02:30 UTC. Change only `settings.json`'s `download_day_utc` value (1–28) to set the monthly download day. Scheduled runs download only on that UTC day. Manual runs through **Actions → Yahoo monthly download → Run workflow** start immediately. Downloaded CSV files are stored as a workflow artifact named `yahoo-monthly-data`; they are not committed back to the repository.

## Run locally

```bash
python -m pip install -r requirements.txt
python download.py
```

The `qc.py`, `check.py`, and their small helper modules are included from the project's QC flow. These legacy QC scripts expect additional historical QC report spreadsheets and are not part of the scheduled download workflow.

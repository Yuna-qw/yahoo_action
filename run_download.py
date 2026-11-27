"""One-command launcher for the original Yahoo downloader."""
import importlib.util
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "settings.json"
DOWNLOADER_PATH = BASE_DIR / "1.yahoo_data_download.py"


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    os.chdir(BASE_DIR)
    os.environ["YAHOO_NEW_CSV_DIR"] = str(config.get("new_data_dir", "/data/yahoo/new_csv"))
    spec = importlib.util.spec_from_file_location("original_yahoo_downloader", DOWNLOADER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.download(
        data_option=0,
        use_threads=int(config.get("use_threads", 1)),
        sleep_time=int(config.get("sleep_time", 1)),
        repeat=int(config.get("repeat", 3)),
        download_option_method=int(config.get("download_method", 1)),
    )


if __name__ == "__main__":
    main()

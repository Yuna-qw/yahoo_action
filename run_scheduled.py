"""Apply the date in settings.json before running the monthly downloader."""
import json
import os
import sys
from datetime import datetime, timezone


def main():
    with open("settings.json", "r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    download_day = int(settings["download_day_utc"])
    if not 1 <= download_day <= 28:
        raise ValueError("download_day_utc must be between 1 and 28")

    manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    today_utc = datetime.now(timezone.utc).day
    if not manual and today_utc != download_day:
        print(f"Skip: today is UTC day {today_utc}; configured download day is {download_day}.")
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output_file:
            output_file.write("should_upload=false\n")
        return

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output_file:
        output_file.write("should_upload=true\n")
    from download import download

    download(data_option=0, use_threads=1, sleep_time=1, repeat=3, download_option_method=1)


if __name__ == "__main__":
    main()

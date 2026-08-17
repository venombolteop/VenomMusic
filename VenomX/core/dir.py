
# All rights reserved.
#
import logging
import os
import sys
import time
from os import listdir, mkdir

from config import TEMP_DB_FOLDER


def dirr():
    assets_folder = "assets"
    downloads_folder = "downloads"
    cache_folder = "cache"

    if assets_folder not in listdir():
        logging.warning(
            f"{assets_folder} Folder not Found. Please clone or fork repository again."
        )
        sys.exit()

    for file in os.listdir():
        if (
            file.endswith(".jpg")
            or file.endswith(".jpeg")
            or file.endswith(".mp3")
            or file.endswith(".png")
            or file.endswith(".session")
            or file.endswith(".session-journal")
        ):
            os.remove(file)

    if downloads_folder not in listdir():
        mkdir(downloads_folder)

    if cache_folder not in listdir():
        mkdir(cache_folder)

    if TEMP_DB_FOLDER not in listdir():
        mkdir(TEMP_DB_FOLDER)

    # Clean stale downloads older than 1 hour on startup
    _clean_downloads(downloads_folder)

    logging.info("Directories Updated.")


def _clean_downloads(folder):
    """Remove download files older than 1 hour to prevent disk fill."""
    try:
        now = time.time()
        cutoff = now - 3600  # 1 hour
        removed = 0
        for f in os.listdir(folder):
            fp = os.path.join(folder, f)
            if os.path.isfile(fp):
                try:
                    mtime = os.path.getmtime(fp)
                    if mtime < cutoff:
                        os.remove(fp)
                        removed += 1
                except Exception:
                    pass
        if removed:
            logging.info(f"Cleaned {removed} stale download(s) from {folder}")
    except Exception as e:
        logging.warning(f"Download cleanup failed: {e}")


if __name__ == "__main__":
    dirr()


# All rights reserved.
#
import logging
import os
import sys
import time
from os import listdir, mkdir

from config import TEMP_DB_FOLDER
from VenomX.logging import SESSION_LOG_NAME


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
    _prune_session_logs(10)

    logging.info("Directories Updated.")
    logging.info("Session log: %s", SESSION_LOG_NAME)


def _prune_session_logs(keep: int):
    """Keep the newest few session logs; a restart every test run adds one each
    time, and nothing reads the old ones."""
    import os as _os

    folder = "logs"
    if not _os.path.isdir(folder):
        return
    logs = sorted(
        f for f in _os.listdir(folder)
        if f.startswith("session-") and f.endswith(".log")
    )
    for name in (logs[:-keep] if len(logs) > keep else []):
        try:
            _os.remove(_os.path.join(folder, name))
        except Exception:
            pass


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

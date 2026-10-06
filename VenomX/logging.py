
# All rights reserved.


import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from config import LOG_FILE_NAME

# One file per run, under logs/. Everything used to land in a single file that
# only ever appended, so a restart buried the previous session under the new
# one and the two became impossible to tell apart — which is exactly when a log
# is needed most. The name carries the start time, so the file for a session is
# known without reading a single line of it.
LOG_DIR = "logs"
SESSION_LOG_NAME = ""


def _session_log_path() -> str:
    global SESSION_LOG_NAME
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(LOG_DIR, exist_ok=True)
    SESSION_LOG_NAME = os.path.join(LOG_DIR, f"session-{stamp}.log")
    return SESSION_LOG_NAME


SESSION_LOG_NAME = _session_log_path()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE_NAME, maxBytes=5000000, backupCount=10),
        RotatingFileHandler(SESSION_LOG_NAME, maxBytes=5000000, backupCount=2),
        logging.StreamHandler(),
    ],
)

logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

# Setting ntgcalls logger level and disabling propagation
ntgcalls_logger = logging.getLogger("ntgcalls")
ntgcalls_logger.setLevel(logging.CRITICAL)
ntgcalls_logger.propagate = False


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)

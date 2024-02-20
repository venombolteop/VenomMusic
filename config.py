import re
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

# Get this value from my.telegram.org/apps
API_ID = int(getenv("API_ID", ""))
API_HASH = getenv("API_HASH", "")

# Get your token from @BotFather on Telegram.
BOT_TOKEN = getenv("BOT_TOKEN", "")

# Get your mongo url from cloud.mongodb.com
MONGO_DB_URI = getenv("MONGO_DB_URI", "")

DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 5400))

SONG_DOWNLOAD_DURATION = int(
    getenv("SONG_DOWNLOAD_DURATION_LIMIT", "5400")
)
# Chat id of a group for logging bot's activities
LOGGER_ID = int(getenv("LOGGER_ID", ""))

# Get this value from @Hot_Girl_Robot on Telegram by /id
OWNER_ID = int(getenv("OWNER_ID", "6306738739"))

## Fill these variables if you're deploying on heroku.
# Your heroku app name
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
# Get it from http://dashboard.heroku.com/account
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

UPSTREAM_REPO = getenv(
    "UPSTREAM_REPO",
    "https://github.com/venombolteop/VenomMusic",
)
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "main")
GIT_TOKEN = getenv(
    "GIT_TOKEN", None
)  # Fill this variable if your upstream repository is private

SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/lundlelobsdk")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/lundlelobsdkmera")

# Set this to True if you want the assistant to automatically leave chats after an interval
AUTO_LEAVING_ASSISTANT = bool(getenv("AUTO_LEAVING_ASSISTANT", "False"))
AUTO_SUGGESTION_MODE = getenv("AUTO_SUGGESTION_MODE", "False")
AUTO_SUGGESTION_TIME = int(
    getenv("AUTO_SUGGESTION_TIME", "5400"))
# Get this credentials from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "4b75b8708dfc478e9f1a37e0a2c024d4")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "7241b5213810432d83923cc18b8bbea5")


# Maximum limit for fetching playlist's track from youtube, spotify, apple links.
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", 25))

CLEANMODE_DELETE_MINS = int(
    getenv("CLEANMODE_MINS", "5"))
# Telegram audio and video file size limit (in bytes)
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 1073741824))
# Checkout https://www.gbmb.org/mb-to-bytes for converting mb to bytes


# Get your pyrogram v2 session from @Venom_string_robot on Telegram
STRING1 = getenv("STRING_SESSION", "")
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)


BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}
chatstats = {}
userstats = {}
clean = {}


START_IMG_URL = getenv(
    "START_IMG_URL", "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
)
PING_IMG_URL = getenv(
    "PING_IMG_URL", "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
)
PLAYLIST_IMG_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
STATS_IMG_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
TELEGRAM_AUDIO_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
TELEGRAM_VIDEO_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
STREAM_IMG_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
SOUNCLOUD_IMG_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
YOUTUBE_IMG_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
SPOTIFY_ARTIST_IMG_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
SPOTIFY_ALBUM_IMG_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"
SPOTIFY_PLAYLIST_IMG_URL = "https://lh3.googleusercontent.com/pw/ABLVV87fU6FgeNJr7q0ebTfn4klgaf1-MHnHkNmahyCY9och-LUKY2NsRyFNI3qw7g9VWTPgoyN6xDfZ6hFXacSa0eNSKy3K1ZFR7574HmDpflveoqjrXweDNcLmYwXcwOxuEbD8JoQgZCAokbF44EcsfOI=w720-h1280-s-no-gm?authuser=0"


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))


DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))
SONG_DOWNLOAD_DURATION_LIMIT = int(
    time_to_seconds(f"{SONG_DOWNLOAD_DURATION}:00"))

if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHANNEL url is wrong. Please ensure that it starts with https://"
        )

if SUPPORT_CHAT:
    if not re.match("(?:http|https)://", SUPPORT_CHAT):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHAT url is wrong. Please ensure that it starts with https://"
        )

# All rights reserved.
#

import os
import asyncio
import shlex
from typing import Tuple

# Force GitPython to use system git and avoid PATH issues
os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = "/usr/bin/git"
os.environ["GIT_PYTHON_REFRESH"] = "quiet"

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

import config
from ..logging import LOGGER


def install_req(cmd: str):
    if os.environ.get("DYNO"):  # Heroku
        LOGGER(__name__).warning("Skipping pip install on Heroku")
        return None
    


def git():
    """
    Safely initialize git, fetch and pull updates from upstream repository.
    This version:
    - Forces GitPython to use /usr/bin/git
    - Avoids duplicate remotes
    - Uses search_parent_directories for Docker/Heroku safety
    - Removes runtime pip install (must be done at build time)
    """

    REPO_LINK = config.UPSTREAM_REPO

    # Build authenticated repo URL if token exists
    if config.GIT_TOKEN:
        GIT_USERNAME = REPO_LINK.split("com/")[1].split("/")[0]
        TEMP_REPO = REPO_LINK.split("https://")[1]
        UPSTREAM_REPO = f"https://{GIT_USERNAME}:{config.GIT_TOKEN}@{TEMP_REPO}"
    else:
        UPSTREAM_REPO = REPO_LINK

    try:
        # Try to load existing repo
        repo = Repo(search_parent_directories=True)
        LOGGER(__name__).info("Git repository found")
    except InvalidGitRepositoryError:
        # Initialize new repo if not found
        LOGGER(__name__).info("No git repository found, initializing...")
        repo = Repo.init()

        # Create origin remote
        origin = repo.create_remote("origin", UPSTREAM_REPO)
        origin.fetch()

        # Create and checkout branch
        repo.create_head(
            config.UPSTREAM_BRANCH,
            origin.refs[config.UPSTREAM_BRANCH],
        )
        repo.heads[config.UPSTREAM_BRANCH].set_tracking_branch(
            origin.refs[config.UPSTREAM_BRANCH]
        )
        repo.heads[config.UPSTREAM_BRANCH].checkout(True)

    except GitCommandError as e:
        LOGGER(__name__).error(f"Git command error: {e}")
        return

    # Work with origin
    try:
        origin = repo.remote("origin")
    except ValueError:
        # If origin does not exist, create it
        origin = repo.create_remote("origin", UPSTREAM_REPO)

    # Fetch latest changes
    try:
        origin.fetch(config.UPSTREAM_BRANCH)
    except GitCommandError as e:
        LOGGER(__name__).error(f"Failed to fetch branch: {e}")
        return

    # Pull changes
    try:
        origin.pull(config.UPSTREAM_BRANCH)
        LOGGER(__name__).info("Repository successfully updated with git pull")
    except GitCommandError:
        # Hard reset if pull fails
        LOGGER(__name__).warning("Git pull failed, resetting to FETCH_HEAD")
        try:
            repo.git.reset("--hard", "FETCH_HEAD")
        except GitCommandError as e:
            LOGGER(__name__).error(f"Git reset failed: {e}")
            return

    LOGGER(__name__).info(f"Fetched Updates from: {REPO_LINK}")

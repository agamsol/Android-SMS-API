import os
import asyncio
import urllib.request
import urllib.error
from dotenv import load_dotenv
from utils.logger import create_logger

load_dotenv()

# Configuration from environment variables
FETCH_UPDATES_FROM_GITHUB = os.getenv("FETCH_UPDATES_FROM_GITHUB", "true").lower() == "true"
GITHUB_UPDATE_URL = os.getenv("GITHUB_UPDATE_URL", "https://raw.githubusercontent.com/agamsol/Android-SMS-API/master/.env.example")
UPDATE_CHECK_INTERVAL_DAYS = int(os.getenv("UPDATE_CHECK_INTERVAL_DAYS", "1"))
CURRENT_VERSION = os.getenv("VERSION", "0.4")
PLAN_RESET_DAY_OF_MONTH = int(os.getenv("PLAN_RESET_DAY_OF_MONTH", "0"))

log = create_logger("UPDATER", logger_name="ASA_UPDATER")

latest_version = None

def _fetch_url_content(url):
    """
    Synchronous helper to fetch URL content using urllib.
    """
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        raise e

async def check_for_updates():
    """
    Fetches the remote .env.example file from GitHub and extracts the VERSION.
    Updates the global `latest_version` variable.
    """
    global latest_version
    
    if not FETCH_UPDATES_FROM_GITHUB:
        log.debug("Update checks are disabled via configuration.")
        return

    log.info(f"Checking for updates from: {GITHUB_UPDATE_URL}")

    try:

        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(None, _fetch_url_content, GITHUB_UPDATE_URL)
        
        remote_version = None
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("VERSION="):
                remote_version = line.split("=", 1)[1].strip()
                break
        
        if remote_version:
            latest_version = remote_version
            if remote_version != CURRENT_VERSION:
                log.info(f"New version available: {remote_version} (Current: {CURRENT_VERSION})")
            else:
                log.debug("Application is up to date.")
        else:
            log.warning("Could not find VERSION key in remote configuration file.")

    except urllib.error.URLError as e:
        log.error(f"Network error while checking for updates: {e}")
    except Exception as e:
        log.error(f"Unexpected error during update check: {e}")

def get_latest_version():
    """Returns the cached latest version."""
    return latest_version

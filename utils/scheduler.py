import os
import time
from datetime import datetime, date
from calendar import monthrange
from dotenv import load_dotenv
from utils.logger import create_logger

load_dotenv()

PLAN_RESET_DAY_OF_MONTH = int(os.getenv("PLAN_RESET_DAY_OF_MONTH", "0"))

log = create_logger("SCHEDULER", logger_name="ASA_SCHEDULER")


def get_billing_cycle_start(reset_day: int = PLAN_RESET_DAY_OF_MONTH) -> int:
    """
    Calculate the Unix timestamp (seconds) for the start of the current billing cycle.

    If reset_day is 0, returns 0 (no filtering — all messages count).
    Otherwise, finds the most recent occurrence of that day:
      - If today >= reset_day: billing started this month on reset_day
      - If today < reset_day: billing started last month on reset_day

    Returns the Unix timestamp at midnight (00:00:00) of the billing cycle start date.
    """

    if reset_day <= 0:
        return 0

    today = date.today()

    if today.day >= reset_day:
        year, month = today.year, today.month
    else:
        if today.month == 1:
            year, month = today.year - 1, 12
        else:
            year, month = today.year, today.month - 1

    _, max_day = monthrange(year, month)
    clamped_day = min(reset_day, max_day)

    cycle_start = datetime(year, month, clamped_day, 0, 0, 0)
    timestamp = int(cycle_start.timestamp())

    log.debug(f"Billing cycle start: {cycle_start.strftime('%Y-%m-%d')} (timestamp: {timestamp}), reset_day={reset_day}")
    return timestamp

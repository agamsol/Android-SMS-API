import os
from datetime import datetime
from calendar import monthrange
from dotenv import load_dotenv
from utils.database import SQLiteDb
from utils.logger import create_logger

load_dotenv()

PLAN_RESET_DAY_OF_MONTH = int(os.getenv("PLAN_RESET_DAY_OF_MONTH", "0"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/Android-SMS-API.db")
db_helper = SQLiteDb(database_path=DATABASE_PATH)
database = db_helper.connect()

log = create_logger("SCHEDULER", logger_name="ASA_SCHEDULER")


def should_run_today(day: int) -> bool:

    if day <= 0:
        return False

    today = datetime.now()

    _, days_in_current_month = monthrange(today.year, today.month)

    target_day = min(int(day), days_in_current_month)

    return today.day == target_day


def monthly_message_reset():

    if should_run_today(PLAN_RESET_DAY_OF_MONTH):
        log.critical(f"Initiating global monthly message count reset. Configured Reset Day: {PLAN_RESET_DAY_OF_MONTH}")
        db_helper.reset_all_messages()

        return True

    return False

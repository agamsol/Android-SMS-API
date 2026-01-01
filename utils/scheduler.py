import os
from datetime import datetime
from calendar import monthrange
from utils.database import SQLiteDb
from dotenv import load_dotenv

load_dotenv()

PLAN_RESET_DAY_OF_MONTH = int(os.getenv("PLAN_RESET_DAY_OF_MONTH", "0"))

db_filename = os.getenv("SQLITE_DATABASE_NAME", "Android-SMS-API")
db_helper = SQLiteDb(database_name=db_filename)
database = db_helper.connect()


def should_run_today(day: int) -> bool:

    if day <= 0:
        return False

    today = datetime.now()

    _, days_in_current_month = monthrange(today.year, today.month)

    target_day = min(int(day), days_in_current_month)

    return today.day == target_day


def monthly_message_reset():

    if should_run_today(PLAN_RESET_DAY_OF_MONTH):
        db_helper.reset_all_messages()

        return True

    return False

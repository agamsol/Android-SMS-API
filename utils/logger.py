import os
import re
import colorama
import io
import sys
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from colorama import Fore, Style

load_dotenv()

LOGGER_LEVEL = os.getenv("LOGGER_LEVEL", "INFO")
LOGGER_PATH = os.getenv("LOGGER_PATH", "data/logs")

log_levels_available = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

colorama.init(autoreset=True)


class DailyFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, log_dir, *args, backupCount=7, **kwargs):
        self.log_dir = log_dir
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"{self.current_date}.log")
        super().__init__(log_file, when="midnight", interval=1, backupCount=backupCount, **kwargs)

    def doRollover(self):
        # Update the file name to match the new date
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.baseFilename = os.path.join(self.log_dir, f"{self.current_date}.log")
        super().doRollover()


class RemoveColorFormatter(logging.Formatter):
    """Formatter that strips ANSI escape sequences (color codes) from log messages."""
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def format(self, record):
        original_message = super().format(record)
        return self.ANSI_ESCAPE.sub('', original_message)


class ColoredFormatter(logging.Formatter):

    LEVEL_COLORS = {
        logging.DEBUG: Fore.BLUE,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def __init__(self, fmt, datefmt=None):
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record):
        level_color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        record.levelname = f"{level_color}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)


def create_logger(
    alias: str,
    log_date_format: str = "%d-%m-%Y %H:%M:%S",
    logs_directory: str = LOGGER_PATH,
    log_level: str = LOGGER_LEVEL,
    logger_name: str = "Android-SMS-API"
) -> logging.Logger:

    logs_path = Path(logs_directory)

    log: logging.Logger = logging.getLogger(logger_name)
    log.propagate = False

    if log.handlers:
        print(f"[LOGGER INIT] Logger '{logger_name}' already initialized with handlers.")
        return log

    log_level_object = log_levels_available.get(log_level)

    log.setLevel(log_level_object)

    os.makedirs(logs_path, exist_ok=True)

    # FILE HANDLER
    file_handler = DailyFileHandler(logs_path, backupCount=7, encoding='utf-8')
    file_handler_formatting = RemoveColorFormatter(f'[%(asctime)s] [{alias}] [%(levelname)-8s] %(message)s')
    file_handler.setFormatter(file_handler_formatting)
    file_handler.setLevel(log_level_object)

    # CONSOLE HANDLER
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    console_handler = logging.StreamHandler(sys.stdout)

    console_handler_formatting = ColoredFormatter(
        fmt=f'{Fore.LIGHTBLACK_EX}[{Fore.LIGHTBLUE_EX}%(asctime)s{Fore.LIGHTBLACK_EX}] {Fore.LIGHTBLACK_EX}[{Fore.LIGHTBLUE_EX}{alias}{Fore.LIGHTBLACK_EX}] [%(levelname)s{Fore.LIGHTBLACK_EX}] {Fore.WHITE}%(message)s',
        datefmt=log_date_format
    )
    console_handler.setFormatter(console_handler_formatting)
    console_handler.setLevel(log_level_object)

    log.addHandler(file_handler)
    log.addHandler(console_handler)

    return log

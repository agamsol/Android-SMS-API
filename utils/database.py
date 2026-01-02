import sqlite3
from pathlib import Path
from utils.logger import create_logger
from utils.models.database import User_Model, Message_Model

log = create_logger("DATABASE", logger_name="ASA_DATABASE")


class SQLiteDb:

    def __init__(self, database_path: str):

        self.database_name = self._validate_database_path(database_path)
        self.conn: sqlite3.Connection = None
        self.messages_table_name = "messages"
        self.users_table_name = "users"

    def _validate_database_path(self, database_path: str) -> str:

        path = Path(database_path)

        if path.suffix != ".db":
            path = path.with_suffix(".db")

        path.parent.mkdir(parents=True, exist_ok=True)

        return str(path)

    def _dict_factory(self, cursor, row):
        """
        Converts SQLite rows (tuples) into Dictionaries to mimic MongoDB documents.
        """
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _create_tables(self):
        """
        Creates necessary tables if they don't exist.
        """

        cursor = self.conn.cursor()

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.users_table_name} (
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                messages_limit INTEGER DEFAULT 0,
                administrator BOOLEAN DEFAULT 0
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.messages_table_name} (
                username TEXT NOT NULL,
                message TEXT,
                sent_to TEXT NOT NULL,
                sent_time INTEGER NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def connect(self, force_database_name: str = None):

        if force_database_name:
            self.database_name = force_database_name

        if not self.database_name:
            log.error("Connection failed: No database path specified.")
            raise ValueError("No database was specified during the connection.")

        self.conn = sqlite3.connect(self.database_name, check_same_thread=False)

        self.conn.row_factory = self._dict_factory

        self._create_tables()

        return self.conn

    def reset_all_messages(self):

        log.warning("Initiating full reset of message history.")
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM messages")

        cursor.execute("DELETE FROM sqlite_sequence WHERE name='messages'")

        self.conn.commit()
        log.info("All messages have been wiped from the database.")

    def get_user(self, username: str):

        log.debug(f"Fetching profile for user: {username}")
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT * FROM {self.users_table_name} WHERE username = ?",
            (username,)
        )

        query = cursor.fetchone()

        if not query:
            log.debug(f"User lookup failed - User not found: {username}")

        return query

    def insert_user(self, user_model: User_Model):

        data = user_model.model_dump(mode="json")
        cursor = self.conn.cursor()

        try:
            log.info(f"Attempting to register new user: {user_model.username}")
            cursor.execute(
                f"""INSERT INTO {self.users_table_name}
                   (username, hashed_password, messages_limit, administrator)
                   VALUES (:username, :hashed_password, :messages_limit, :administrator)""",
                data
            )
            self.conn.commit()
            log.info(f"User registration successful: {user_model.username}")

            return

        except sqlite3.IntegrityError:
            log.warning(f"Registration failed - Username already exists: {user_model.username}")
            return None

    def change_password(self, username: str, new_password: str):

        log.info(f"Attempting password change for: {username}")
        current_user = self.get_user(username)

        if current_user:
            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE {self.users_table_name} SET hashed_password = ? WHERE username = ?",
                (new_password, username)
            )
            self.conn.commit()
            log.info(f"Password updated successfully for: {username}")
        else:
            log.warning(f"Password update failed - User not found: {username}")

        return current_user

    def update_message_limit(self, username: str, messages_limit: int):

        log.info(f"Updating message limit for {username} to {messages_limit}")
        current_user = self.get_user(username)

        if current_user:

            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE {self.users_table_name} SET messages_limit = ? WHERE username = ?",
                (messages_limit, username)
            )
            self.conn.commit()
            log.info(f"Message limit updated for {username}.")
        else:
            log.warning(f"Message limit update failed - User not found: {username}")

        return current_user

    def delete_account(self, username: str):

        log.warning(f"Request received to delete account: {username}")
        current_user = self.get_user(username)

        if current_user:
            cursor = self.conn.cursor()
            cursor.execute(
                f"DELETE FROM {self.users_table_name} WHERE username = ?",
                (username,)
            )
            self.conn.commit()
            log.critical(f"Account permanently deleted: {username}")
        else:
            log.warning(f"Account deletion failed - User not found: {username}")

        return current_user

    def count_messages(self, username: str) -> int:

        cursor = self.conn.cursor()

        cursor.execute(
            f"SELECT COUNT(*) as count FROM {self.messages_table_name} WHERE username = ?",
            (username,)
        )

        result = cursor.fetchone()
        count = result['count'] if result else 0

        log.debug(f"Message count for {username}: {count}")
        return count

    def insert_message(self, message_model: Message_Model) -> None:
        data = message_model.model_dump(mode="json")

        log.debug(f"Inserting message. User: {message_model.username}, To: {message_model.sent_to}, Expires: {message_model.expires_at}")

        cursor = self.conn.cursor()

        cursor.execute(
            f"""INSERT INTO {self.messages_table_name}
               (username, message, sent_to, sent_time, expires_at)
               VALUES (:username, :message, :sent_to, :sent_time, :expires_at)""",
            data
        )
        self.conn.commit()

        return

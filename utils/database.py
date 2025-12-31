import sqlite3
from utils.models.database import User_Model, Message_Model


class SQLiteDb:

    def __init__(self, database_name: str):

        self.database_name: str = database_name if database_name.endswith(".db") else f"{database_name}.db"
        self.conn: sqlite3.Connection = None

        self.messages_table_name = "messages"
        self.users_table_name = "users"

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

    def connect(
        self,
        force_database_name: str = None,
        server_selection_timeout: int = 10000
    ):
        if force_database_name:
            self.database_name = force_database_name

        if not self.database_name:
            raise ValueError("No database was specified during the connection.")

        self.conn = sqlite3.connect(self.database_name, check_same_thread=False)

        self.conn.row_factory = self._dict_factory

        self._create_tables()

        return self.conn

    def get_user(self, username: str):

        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT * FROM {self.users_table_name} WHERE username = ?",
            (username,)
        )

        query = cursor.fetchone()

        return query

    def insert_user(self, user_model: User_Model):

        data = user_model.model_dump(mode="json")
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                f"""INSERT INTO {self.users_table_name}
                   (username, hashed_password, messages_limit, administrator)
                   VALUES (:username, :hashed_password, :messages_limit, :administrator)""",
                data
            )
            self.conn.commit()

            return

        except sqlite3.IntegrityError:
            return None

    def change_password(self, username: str, new_password: str):

        current_user = self.get_user(username)

        if current_user:
            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE {self.users_table_name} SET hashed_password = ? WHERE username = ?",
                (new_password, username)
            )
            self.conn.commit()

        return current_user

    def update_message_limit(self, username: str, messages_limit: int):

        current_user = self.get_user(username)

        if current_user:

            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE {self.users_table_name} SET messages_limit = ? WHERE username = ?",
                (messages_limit, username)
            )
            self.conn.commit()

        return current_user

    def delete_account(self, username: str):

        current_user = self.get_user(username)

        if current_user:
            cursor = self.conn.cursor()
            cursor.execute(
                f"DELETE FROM {self.users_table_name} WHERE username = ?",
                (username,)
            )
            self.conn.commit()

        return current_user

    def count_messages(self, username: str) -> int:

        cursor = self.conn.cursor()

        cursor.execute(
            f"SELECT COUNT(*) as count FROM {self.messages_table_name} WHERE username = ?",
            (username,)
        )

        result = cursor.fetchone()

        return result['count'] if result else 0

    def insert_message(self, message_model: Message_Model) -> None:
        data = message_model.model_dump(mode="json")
        cursor = self.conn.cursor()

        cursor.execute(
            f"""INSERT INTO {self.messages_table_name}
               (username, message, sent_to, sent_time, expires_at)
               VALUES (:username, :message, :sent_to, :sent_time, :expires_at)""",
            data
        )
        self.conn.commit()

        return

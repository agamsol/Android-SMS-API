import sqlite3
import os
from pathlib import Path
from utils.logger import create_logger
from utils.models.database import User_Model, Message_Model, APITokenInDB

log = create_logger("DATABASE", logger_name="ASA_DATABASE")


class SQLiteDb:

    def __init__(self, database_path: str):

        self.database_name = self._validate_database_path(database_path)
        self.conn: sqlite3.Connection = None
        self.messages_table_name = "messages"
        self.users_table_name = "users"
        self.tokens_table_name = "api_tokens"

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
            CREATE TABLE IF NOT EXISTS {self.messages_table_name} (
                username TEXT NOT NULL,
                message TEXT,
                sent_to TEXT NOT NULL,
                sent_time INTEGER NOT NULL,
                token_id TEXT DEFAULT NULL,
                FOREIGN KEY(token_id) REFERENCES {self.tokens_table_name}(id)
            )
        """)

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.tokens_table_name} (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                messages_limit INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

        # Migrations  

        # from 0.3 to 0.4: Add token_id column to messages table
        cursor.execute(f"PRAGMA table_info({self.messages_table_name})")
        
        columns = [info['name'] for info in cursor.fetchall()]
        
        if "token_id" not in columns:
            if os.getenv("MIGRATE_DATABASE", "False").lower() != "true":
                log.critical("DATABASE MIGRATION REQUIRED! The 'token_id' column is missing in the 'messages' table.")
                log.critical("To apply the migration, set the environment variable MIGRATE_DATABASE=True and restart the application.")
                
                os._exit(1)
            else:

                log.info("Migrating database: Adding token_id column to messages table.")
                try:
                    cursor.execute(f"ALTER TABLE {self.messages_table_name} ADD COLUMN token_id TEXT DEFAULT NULL REFERENCES {self.tokens_table_name}(id)")
                    self.conn.commit()
                    log.info("Migration successful: Added token_id column.")


                    # from 0.3 to 0.4: Remove users table (deprecated)
                    cursor.execute(f"DROP TABLE IF EXISTS {self.users_table_name}")
                    self.conn.commit()
                
                except sqlite3.OperationalError as e:
                    log.error(f"Migration failed: {e}")

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
        cursor.execute(f"DELETE FROM {self.messages_table_name} ")

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

    def get_all_users(self):

        log.debug("Fetching all users")
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {self.users_table_name}")

        return cursor.fetchall()

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

        log.debug(f"Inserting message. User: {message_model.username}, To: {message_model.sent_to}, Token: {message_model.token_id}")

        cursor = self.conn.cursor()

        cursor.execute(
            f"""INSERT INTO {self.messages_table_name}
               (username, message, sent_to, sent_time, token_id)
               VALUES (:username, :message, :sent_to, :sent_time, :token_id)""",
            data
        )
        self.conn.commit()

        return

    def create_token(self, token_model: APITokenInDB):

        data = token_model.model_dump(mode="json")
        cursor = self.conn.cursor()

        try:
            log.info(f"Creating new API Token: {token_model.name} ({token_model.id})")
            cursor.execute(
                f"""INSERT INTO {self.tokens_table_name}
                   (id, name, token_hash, messages_limit, is_active, created_at)
                   VALUES (:id, :name, :token_hash, :messages_limit, :is_active, :created_at)""",
                data
            )
            self.conn.commit()
            log.info(f"Token creation successful: {token_model.id}")
            return token_model

        except sqlite3.IntegrityError:
            log.error(f"Token creation failed - ID conflict: {token_model.id}")
            return None

    def get_token_by_id(self, token_id: str):

        log.debug(f"Fetching token metadata: {token_id}")
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT * FROM {self.tokens_table_name} WHERE id = ?",
            (token_id,)
        )
        return cursor.fetchone()
    
    def get_all_tokens(self):

        log.debug("Fetching all API tokens")
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {self.tokens_table_name}")
        return cursor.fetchall()

    def update_token(self, token_id: str, limit: int = None, active: bool = None):

        updates = []
        params = []

        if limit is not None:
            updates.append("messages_limit = ?")
            params.append(limit)
        
        if active is not None:
            updates.append("is_active = ?")
            params.append(active)
        
        if not updates:
            return None
        
        params.append(token_id)

        query = f"UPDATE {self.tokens_table_name} SET {', '.join(updates)} WHERE id = ?"

        cursor = self.conn.cursor()
        cursor.execute(query, tuple(params))
        self.conn.commit()
        
        log.info(f"Updated token {token_id}. Changes: Limit={limit}, Active={active}")
        return self.get_token_by_id(token_id)

    def revoke_token(self, token_id: str):
        return self.update_token(token_id, active=False)

    def delete_token(self, token_id: str):
        
        log.warning(f"Deleting token: {token_id}")
        cursor = self.conn.cursor()
        cursor.execute(f"DELETE FROM {self.tokens_table_name} WHERE id = ?", (token_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def count_token_messages(self, token_id: str) -> int:

        cursor = self.conn.cursor()
        
        cursor.execute(
            f"SELECT COUNT(*) as count FROM {self.messages_table_name} WHERE token_id = ?",
            (token_id,)
        ) 

        result = cursor.fetchone()
        return result['count'] if result else 0

    def refresh_token_id(self, token_id: str, new_hash: str):

        log.info(f"Refreshing token hash for {token_id}")
        
        cursor = self.conn.cursor()
        
        try:
            cursor.execute(
                f"UPDATE {self.tokens_table_name} SET token_hash = ? WHERE id = ?",
                (new_hash, token_id)
            )
            self.conn.commit()
            
            if cursor.rowcount == 0:
                 return None
                 
            log.info(f"Token hash updated for {token_id}")
            return self.get_token_by_id(token_id)

        except sqlite3.Error as e:
            self.conn.rollback()
            log.error(f"Token refresh failed: {e}")
            return None

from pymongo import MongoClient, database

from utils.models.mongodb import User_Model, Message_Model


class MongoDb:

    def __init__(self, database_name: str):
        self.database_name: str = database_name
        self.host: str = None
        self.port: int = None
        self.username: str = None
        self.client: MongoClient = None
        self.database: database.Database = None

        self.messages_collection_name = "messages"
        self.users_collection_name = "users"

    def connect(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        force_database_name: str = None,
        server_selection_timeout: int = 10000
    ) -> database.Database:

        if force_database_name:

            self.database_name: str = force_database_name

        if not self.database_name:
            raise ValueError("No database was specified during the connection.")

        self.host = host
        self.port = port
        self.username = username

        mongo_client = MongoClient(
            host=host,
            port=port,
            username=username,
            password=password,
            ServerSelectionTimeoutMS=server_selection_timeout
        )

        self.client = mongo_client
        self.database = mongo_client[self.database_name]

        return mongo_client[self.database_name]

    def get_user(self, username: str):

        query = self.database[self.users_collection_name].find_one(
            filter={"username": username}
        )

        return query

    def insert_user(self, user_model: User_Model):

        user_payload = self.database[self.users_collection_name].insert_one(
            user_model.model_dump(mode="json")
        )

        return user_payload

    def change_password(self, username: str, new_password: str):

        user_password_changed = self.database[self.users_collection_name].find_one_and_update(
            filter={"username": username},
            update={"$set": {"hashed_password": new_password}}
        )

        return user_password_changed

    def update_message_limit(self, username: str, messages_limit: int):

        user_updated = self.database[self.users_collection_name].find_one_and_update(
            filter={"username": username},
            update={"$set": {"messages_limit": messages_limit}}
        )

        return user_updated

    def delete_account(self, username: str):

        deleted_user = self.database[self.users_collection_name].find_one_and_delete(
            filter={"username": username}
        )

        return deleted_user

    def count_messages(self, username: str) -> int:

        messages_amount = self.database[self.messages_collection_name].count_documents(
            filter={"username": username}
        )

        return messages_amount

    def insert_message(self, message_model: Message_Model):

        message_payload = self.database[self.messages_collection_name].insert_one(
            message_model.model_dump(mode="json")
        )

        return message_payload

import os
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
from utils.adb import Adb  # noqa: F401
from utils.mongodb import MongoDb
from routes import health, authentication

load_dotenv()

ADB_PATH = os.path.join("src", "bin", "adb.exe" if os.name == 'win' else 'adb')

mongodb_helper = MongoDb(
    database_name=os.getenv("MONGODB_DATABASE_NAME")
)

mongodb = mongodb_helper.connect(
    host=os.getenv("MONGODB_HOST"),
    port=int(os.getenv("MONGODB_PORT")),
    username=os.getenv("MONGODB_USERNAME"),
    password=os.getenv("MONGODB_PASSWORD")
)

app = FastAPI(
    title="Android-SMS-API",
    description="Turn your Android phone into a programmable SMS server. A lightweight HTTP API wrapper around ADB for sending text messages over cellular network"
)

app.include_router(
    router=health.router,
    tags=["Health"]
)

app.include_router(
    router=authentication.router,
    tags=["Authentication"]
)

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)

import uvicorn
from fastapi import FastAPI
from routes import status

app = FastAPI()

app.include_router(status.router)

# Authentication
# ADB

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

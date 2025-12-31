import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
from utils.adb import Adb  # noqa: F401
from utils.database import SQLiteDb
from routes import health, authentication, adb
from routes.adb import adb as adb_library
from models.errors import ErrorResponse

load_dotenv()

ADB_AUTO_CONNECT = os.getenv("ADB_AUTO_CONNECT", "false").lower() == "true"
ADB_DEFAULT_DEVICE = os.getenv("ADB_DEFAULT_DEVICE")

db_filename = os.getenv("SQLITE_DATABASE_NAME", "Android-SMS-API")
db_helper = SQLiteDb(database_name=db_filename)
database = db_helper.connect()


@asynccontextmanager
async def lifespan(app: FastAPI):

    if ADB_AUTO_CONNECT and ADB_DEFAULT_DEVICE:

        try:
            print(f"Auto-connecting to {ADB_DEFAULT_DEVICE}...")

            result = await adb_library.connect_device(ADB_DEFAULT_DEVICE)

            response_detail = "ADB Error while connecting to device!"

            if "connected" in result.stdout or "already" in result.stdout:

                response_detail = "ADB is now connected to device"

            print(f"ADB Connection Status: {response_detail}")

        except Exception as e:
            print(f"Failed to auto-connect to ADB: {e}")

    yield


app = FastAPI(
    title="Android-SMS-API",
    description="Turn your Android phone into a programmable SMS server. A lightweight HTTP API wrapper around ADB for sending text messages over cellular network",
    lifespan=lifespan,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Bad Request - Invalid input or validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Username already registered",
                        "status_code": 400,
                        "error_type": "BadRequest"
                    }
                }
            }
        },
        401: {
            "model": ErrorResponse,
            "description": "Unauthorized - Invalid or missing authentication credentials",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Could not validate credentials",
                        "status_code": 401,
                        "error_type": "Unauthorized"
                    }
                }
            }
        },
        403: {
            "model": ErrorResponse,
            "description": "Forbidden - Insufficient permissions or operation not allowed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You are not authorized to perform this action!",
                        "status_code": 403,
                        "error_type": "Forbidden"
                    }
                }
            }
        },
        404: {
            "model": ErrorResponse,
            "description": "Not Found - Resource does not exist",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Account not found",
                        "status_code": 404,
                        "error_type": "NotFound"
                    }
                }
            }
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal Server Error - Server-side error occurred",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Internal server error occurred while processing your request",
                        "status_code": 500,
                        "error_type": "InternalServerError"
                    }
                }
            }
        }
    }
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Global handler for HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "error_type": _get_error_type(exc.status_code)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Global handler for validation errors"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Validation error: " + str(exc.errors()),
            "status_code": 400,
            "error_type": "ValidationError"
        }
    )


def _get_error_type(status_code: int) -> str:
    """Map HTTP status codes to error types"""
    error_types = {
        400: "BadRequest",
        401: "Unauthorized",
        403: "Forbidden",
        404: "NotFound",
        500: "InternalServerError"
    }
    return error_types.get(status_code, "Error")


app.include_router(
    router=health.router,
    tags=["Health"]
)

app.include_router(
    router=authentication.router,
    prefix="/auth"
)

app.include_router(
    router=adb.router,
    prefix="/adb"
)

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8001)

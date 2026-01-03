import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
from utils.database import SQLiteDb
from routes import health, authentication, adb
from routes.authentication import ADMIN_USERNAME, ADMIN_PASSWORD
from routes.adb import adb as adb_library
from models.errors import ErrorResponse
from utils.logger import create_logger
from apscheduler.schedulers.background import BackgroundScheduler
from utils.adb_wireless import start_terminal_pairing_session
from utils.scheduler import monthly_message_reset
load_dotenv()

ADB_QR_DEVICE_PAIRING = os.getenv("ADB_QR_DEVICE_PAIRING", "true").lower() == "true"
ADB_AUTO_CONNECT = os.getenv("ADB_AUTO_CONNECT", "false").lower() == "true"
ADB_DEFAULT_DEVICE = os.getenv("ADB_DEFAULT_DEVICE")
PLAN_RESET_DAY_OF_MONTH = int(os.getenv("PLAN_RESET_DAY_OF_MONTH", "0"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/Android-SMS-API.db")

db_helper = SQLiteDb(database_path=DATABASE_PATH)
database = db_helper.connect()

log = create_logger(alias="APP", logger_name="ASA_APP")


@asynccontextmanager
async def lifespan(app: FastAPI):

    log.info("Application startup: Initializing background services.")

    if PLAN_RESET_DAY_OF_MONTH != 0:

        scheduler = BackgroundScheduler()
        scheduler.add_job(monthly_message_reset, 'cron', hour=0, minute=0)
        scheduler.start()

        log.info("Background scheduler started. Monthly reset job scheduled.")

    connection_failed = False

    if ADB_AUTO_CONNECT and ADB_DEFAULT_DEVICE:

        log.info(f"ADB Auto-Connect enabled. Attempting to connect to default device: {ADB_DEFAULT_DEVICE}")
        try:
            await adb_library.connect_device(ADB_DEFAULT_DEVICE)
        except Exception as e:
            log.error(f"Auto-connect failed: {str(e)}")
            connection_failed = True

    if (connection_failed and ADB_QR_DEVICE_PAIRING) or (not ADB_AUTO_CONNECT and ADB_QR_DEVICE_PAIRING):

        log.debug("Starting terminal-based QR pairing session as per configuration.")
        start_terminal_pairing_session(300)

    log.info(f"Admin Credentials: Username='{ADMIN_USERNAME}' Password='{ADMIN_PASSWORD}'")
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

    log.warning(f"HTTP Exception encountered. Status: {exc.status_code}, Detail: {exc.detail}, Path: {request.url.path}")

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

    log.warning(f"Request validation failed. Path: {request.url.path}, Errors: {str(exc.errors())}")

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

    log.info("Starting Uvicorn server environment...")
    uvicorn.run(app, host="0.0.0.0", port=8001)

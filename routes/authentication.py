import os
import hashlib
from dotenv import load_dotenv, set_key
from typing import Annotated
from fastapi import Depends, HTTPException, status, APIRouter
from jose.exceptions import JWTError
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from models.authentication import Token, AdditionalAccountData, LoginObtainToken, login_obtain_token, MUST_BE_ADMINISTRATOR_EXCEPTION, generate_random_password, ResetPasswordRequest, ResetPasswordResponse, DEFAULT_PASSWORD
from utils.database import SQLiteDb
from utils.secure import JWToken
from utils.scheduler import get_billing_cycle_start, get_billing_cycle_end

ENV_PATH = ".env"
load_dotenv(ENV_PATH)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:

    ADMIN_PASSWORD = DEFAULT_PASSWORD

set_key(dotenv_path=ENV_PATH, key_to_set="ADMIN_PASSWORD", value_to_set=ADMIN_PASSWORD)


def get_admin_password() -> str:
    """Read the current admin password from .env (source of truth)."""

    load_dotenv(ENV_PATH, override=True)

    return os.getenv("ADMIN_PASSWORD", DEFAULT_PASSWORD)

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/Android-SMS-API.db")
db_helper = SQLiteDb(database_path=DATABASE_PATH)
database = db_helper.connect()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
router = APIRouter()

async def authenticate_with_token(
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    api_key: Annotated[str | None, Depends(api_key_header)] = None
) -> AdditionalAccountData:
    """
    Verifies the request has a valid token (Admin JWT or API Token).
    Supports Bearer token (Admin/API) and X-API-Key header (API).
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token:

        try:

            token_data = await JWToken.verify(token)

            if token_data.username == ADMIN_USERNAME:

                admin_usage = await db_helper.count_token_messages(ADMIN_USERNAME, since_timestamp=get_billing_cycle_start())

                return AdditionalAccountData(
                    administrator=True,
                    messages_limit=0,
                    messages_sent=admin_usage,
                    next_plan_reset=get_billing_cycle_end(),
                    token_id=ADMIN_USERNAME
                )

        except (ValueError, JWTError):
            pass 

        try:
            token_id = await JWToken.verify_api_token(token)
            record = await db_helper.get_token_by_id(token_id)
            
            if record:

                token_hash = hashlib.sha256(token.encode()).hexdigest()
                if token_hash != record['token_hash']:
                    raise HTTPException(status_code=401, detail="Token has been refreshed and this version is invalid.")

                if not record['is_active']:
                    raise HTTPException(status_code=403, detail="Token has been revoked")
                    
                usage = await db_helper.count_token_messages(token_id, since_timestamp=get_billing_cycle_start())

                return AdditionalAccountData(
                    administrator=False,
                    messages_limit=record['messages_limit'],
                    messages_sent=usage,
                    next_plan_reset=get_billing_cycle_end(),
                    token_id=token_id
                )
        except (ValueError, JWTError):
            pass

    if api_key:

        try:
            token_id = await JWToken.verify_api_token(api_key)

            record = await db_helper.get_token_by_id(token_id)
            
            if not record:
                 raise credentials_exception
            
            token_hash = hashlib.sha256(api_key.encode()).hexdigest()
            if token_hash != record['token_hash']:
                raise HTTPException(status_code=401, detail="Token has been refreshed and this version is invalid.")

            if not record['is_active']:
                 raise HTTPException(status_code=403, detail="Token has been revoked")
                 
            usage = await db_helper.count_token_messages(token_id, since_timestamp=get_billing_cycle_start())
            
            return AdditionalAccountData(
                administrator=False,
                messages_limit=record['messages_limit'],
                messages_sent=usage,
                next_plan_reset=get_billing_cycle_end(),
                token_id=token_id
            )
            
        except (ValueError, JWTError):
            pass
             
    raise credentials_exception


@router.get(
    "/@me",
    response_model=AdditionalAccountData,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Get current account/token details",
    description="Returns details about the currently authenticated entity (User or API Token). Includes message limits and remaining quota for API Tokens."
)
async def get_current_user(
    current_user: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):

    return current_user

@router.post(
    "/login",
    response_model=Token,
    tags=["Authentication"]
)
async def login_for_access_token(
    credentials: Annotated[LoginObtainToken, Depends(login_obtain_token)]
):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials.username == ADMIN_USERNAME:

        current_password = get_admin_password()

        if credentials.password != current_password:
            raise credentials_exception

        if current_password == DEFAULT_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password must be changed before logging in. Use PATCH /auth/reset-password to set a new password.",
            )

        access_token = await JWToken.create(username=ADMIN_USERNAME, remember_me=credentials.remember_me)

        return Token(
            access_token=access_token,
            token_type="bearer"
        )

    raise credentials_exception


@router.patch(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"],
    summary="Reset admin password",
    description="Reset the admin password. Authenticate either via a valid JWT token (Bearer header) or by providing the current default password ('123456') in the request body."
)
async def reset_password(
    body: ResetPasswordRequest,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
):
    authenticated = False

    current_password = get_admin_password()

    if token:

        try:
            token_data = await JWToken.verify(token)

            if token_data.username == ADMIN_USERNAME:
                authenticated = True
        except (ValueError, JWTError):
            pass

    if not authenticated and body.current_password:

        if current_password == DEFAULT_PASSWORD and body.current_password == DEFAULT_PASSWORD:
            authenticated = True

    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Provide a valid JWT token or the current default password.",
        )

    set_key(
        dotenv_path=ENV_PATH,
        key_to_set="ADMIN_PASSWORD",
        value_to_set=body.new_password
    )

    return ResetPasswordResponse(
        detail="Password has been reset successfully."
    )

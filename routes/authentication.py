import os
import hashlib
from dotenv import load_dotenv, set_key
from typing import Annotated
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from models.authentication import Token, AdditionalAccountData, LoginObtainToken, login_obtain_token,  MUST_BE_ADMINISTRATOR_EXCEPTION, generate_random_password
from utils.database import SQLiteDb
from utils.secure import JWToken
from utils.scheduler import get_billing_cycle_start, get_billing_cycle_end

load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:

    ADMIN_PASSWORD = generate_random_password()

    set_key(
        dotenv_path=".env",
        key_to_set="ADMIN_PASSWORD",
        value_to_set=ADMIN_PASSWORD
    )

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

                admin_usage = await db_helper.count_messages(ADMIN_USERNAME, since_timestamp=get_billing_cycle_start())

                return AdditionalAccountData(
                    username=token_data.username,
                    messages_limit=0,
                    administrator=True,
                    messages_sent=admin_usage,
                    next_reset=get_billing_cycle_end(),
                    token_id=None
                )

        except ValueError:
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
                    username=record['name'], 
                    messages_limit=record['messages_limit'],
                    administrator=False,
                    messages_sent=usage,
                    messages_left=record['messages_limit'] - usage,
                    next_reset=get_billing_cycle_end(),
                    token_id=token_id
                )
        except ValueError:
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
                username=record['name'], 
                messages_limit=record['messages_limit'],
                administrator=False,
                messages_sent=usage,
                messages_left=record['messages_limit'] - usage,
                next_reset=get_billing_cycle_end(),
                token_id=token_id
            )
            
        except ValueError:
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

        if not ((credentials.username == ADMIN_USERNAME) and (credentials.password == ADMIN_PASSWORD)):
            raise credentials_exception

        access_token = await JWToken.create(username=ADMIN_USERNAME, remember_me=credentials.remember_me)

        return Token(
            access_token=access_token,
            token_type="bearer"
        )

    raise credentials_exception




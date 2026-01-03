import os
from dotenv import load_dotenv, set_key
from typing import Annotated
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer
from models.authentication import CreateUser, Token, AdditionalAccountData, CreateUserParams, LoginObtainToken, login_obtain_token, AccountConfirmationResponse, BaseUser, MUST_BE_ADMINISTRATOR_EXCEPTION, ResetAccountPasswordRequest, UpdateMessageLimitRequest, MessageLimitUpdateResponse, generate_random_password
from utils.models.database import User_Model
from utils.database import SQLiteDb
from utils.secure import JWToken, Hash

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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter()


async def authenticate_with_token(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> AdditionalAccountData:
    """This function verifies that the request has a valid token input"""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:

        token_data = await JWToken.verify(token)

    except ValueError:
        raise credentials_exception

    if token_data.username == ADMIN_USERNAME:

        return AdditionalAccountData(
            username=token_data.username,
            messages_limit=0,
            administrator=True
        )

    user = db_helper.get_user(token_data.username)

    if user is None:
        raise credentials_exception

    return AdditionalAccountData(
        **user
    )


@router.get(
    "/@me",
    response_model=AdditionalAccountData,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"]
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

        access_token = await JWToken.create(username=ADMIN_USERNAME)

        return Token(
            access_token=access_token,
            token_type="bearer"
        )

    user_payload: dict = db_helper.get_user(username=credentials.username)

    if not user_payload:
        raise credentials_exception

    verified_user = await Hash.verify_password(credentials.password, user_payload.get("hashed_password"))

    if not verified_user:
        raise credentials_exception

    access_token = await JWToken.create(username=credentials.username)

    return Token(
        access_token=access_token,
        token_type="bearer"
    )


@router.post(
    "/create-account",
    summary="Create an account with a monthly limitted messages cap",
    response_model=AdditionalAccountData,
    status_code=status.HTTP_201_CREATED,
    tags=["Account Management"]
)
async def create_account(
    token: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    body: CreateUserParams,
):

    username = body.username
    password = body.password
    messages_limit = body.messages_limit
    administrator = body.administrator

    password_data = CreateUser(username=username, password=password)
    credentials = AdditionalAccountData(
        username=username,
        messages_limit=messages_limit,
        administrator=administrator
    )

    if not token.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    if db_helper.get_user(credentials.username) or credentials.username == ADMIN_PASSWORD:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    hashed_password = await Hash.create(password_data.password)

    user_payload = User_Model(
        username=credentials.username,
        hashed_password=hashed_password,
        messages_limit=credentials.messages_limit,
        administrator=credentials.administrator
    )

    db_helper.insert_user(user_payload)

    return user_payload


@router.put(
    "/reset-password",
    summary="Reset password for a specific account. Users can reset their own password without administrator privileges.",
    response_model=AccountConfirmationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Account Management"]
)
async def reset_account_password(
    token: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    body: ResetAccountPasswordRequest,
):

    # USER IS ALLOWED TO RESET ITS OWN PASSWORD WITHOUT ADMINISTRATOR PERMISSION WHILE ADMINISTRATORS CAN ALSO RESET ITS PASSWORD
    if not token.administrator and token.username != body.username:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    if body.username == ADMIN_USERNAME:

        raise HTTPException(
            detail=f"Cannot reset password for '{ADMIN_USERNAME}' account. It is a hardcoded system user; change it in the config file",
            status_code=status.HTTP_403_FORBIDDEN
        )

    user = db_helper.get_user(body.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    password_data = CreateUser(username=body.username, password=body.password)

    hashed_password = await Hash.create(password_data.password)

    account_password_changed = db_helper.change_password(password_data.username, hashed_password)

    if not account_password_changed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )

    return AccountConfirmationResponse(
        username=body.username,
        detail="Account password has been changed"
    )


@router.put(
    "/message-limit",
    summary="Update monthly message limit for a user",
    response_model=MessageLimitUpdateResponse,
    status_code=status.HTTP_200_OK,
    tags=["Account Management"]
)
async def update_message_limit(
    token: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    body: UpdateMessageLimitRequest,
):

    if not token.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    if body.username == ADMIN_USERNAME:

        raise HTTPException(
            detail=f"Cannot update message limit for '{ADMIN_USERNAME}' account. It is a hardcoded system user",
            status_code=status.HTTP_403_FORBIDDEN
        )

    user = db_helper.get_user(body.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    account_updated = db_helper.update_message_limit(body.username, body.messages_limit)

    if not account_updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update message limit"
        )

    return MessageLimitUpdateResponse(
        username=body.username,
        detail="Message limit has been updated",
        messages_limit=body.messages_limit
    )


@router.delete(
    "/delete-account",
    summary="",
    response_model=AccountConfirmationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Account Management"]
)
async def delete_account(
    token: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    username: BaseUser
):

    if not token.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    # PREVENT/HANDLE HARDCODED USER DELETION
    if token.username == ADMIN_USERNAME:

        raise HTTPException(
            detail=f"Cannot delete the '{ADMIN_USERNAME}' account because it is a hardcoded system user",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # PREVENT SELF ACCOUNT DELETION
    if token.username == username:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete your own account"
        )

    account_deleted = db_helper.delete_account(username)

    if not account_deleted:

        return AccountConfirmationResponse(
            username=username,
            detail="Account not found or could not be deleted"
        )

    return AccountConfirmationResponse(
        username=username,
        detail="Account has been deleted"
    )

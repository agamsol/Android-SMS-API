import os
from dotenv import load_dotenv
from typing import Literal, Annotated, Dict, Any  # noqa: F401
from pydantic import BaseModel, Field  # noqa: F401
from fastapi import Depends, HTTPException, status, APIRouter, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from models.authentication import CreateUser, Token, AdditionalAccountData, CreateUserParams, LoginObtainToken, login_obtain_token
from utils.models.mongodb import User_Model
from utils.mongodb import MongoDb
from utils.secure import JWToken, Hash

load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

mongodb_helper = MongoDb(
    database_name=os.getenv("MONGODB_DATABASE_NAME")
)

mongodb = mongodb_helper.connect(
    host=os.getenv("MONGODB_HOST"),
    port=int(os.getenv("MONGODB_PORT")),
    username=os.getenv("MONGODB_USERNAME"),
    password=os.getenv("MONGODB_PASSWORD")
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# POST Create Users
# PUT user limit
# POST Create token
# DELETE Delete Users

router = APIRouter(
    prefix="/auth",
)


async def authenticate_with_token(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Dict[str, Any]:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    print(token)

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

    user = mongodb_helper.get_user(token_data.username)

    if user is None:
        raise credentials_exception

    return AdditionalAccountData(
        **user
    )


@router.post(
    "/login",
    response_model=Token
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

    user_payload: dict = mongodb_helper.get_user(username=credentials.username)

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
    status_code=status.HTTP_201_CREATED
)
async def create_account(
    token: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    create_user_form: Annotated[CreateUserParams, Depends()],
):

    username = create_user_form.username
    password = create_user_form.password
    messages_limit = create_user_form.messages_limit
    administrator = create_user_form.administrator

    password_data = CreateUser(username=username, password=password)
    credentials = AdditionalAccountData(
        username=username,
        messages_limit=messages_limit,
        administrator=administrator
    )

    # ONLY ADMINISTRATOR ACCOUNTS CAN CREATE NEW ACCOUNTS
    print(token)
    if not token.administrator:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not authorized to create new accounts."
        )

    if mongodb_helper.get_user(credentials.username) or credentials.username == ADMIN_PASSWORD:

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

    mongodb_helper.insert_user(user_payload)

    return user_payload


@router.get(
    "/@me",
    response_model=AdditionalAccountData,
    status_code=status.HTTP_200_OK
)
async def get_current_user(
    current_user: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):

    return current_user

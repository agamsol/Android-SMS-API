import os
from jose import JWTError, jwt
from dotenv import load_dotenv
from typing import Literal, Annotated, Dict, Any  # noqa: F401
from pydantic import BaseModel, Field  # noqa: F401
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from models.authentication import TokenData
from utils.mongodb import MongoDb


load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not set in .env")

mongodb_helper = MongoDb(
    database_name=os.getenv("MONGODB_DATABASE_NAME")
)

mongodb = mongodb_helper.connect(
    host=os.getenv("MONGODB_HOST"),
    port=int(os.getenv("MONGODB_PORT")),
    username=os.getenv("MONGODB_USERNAME"),
    password=os.getenv("MONGODB_PASSWORD")
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# POST Create Users
# PUT user limit
# POST Create token
# DELETE Delete Users


async def authentication_with_token(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Dict[str, Any]:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:

        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        username: str | None = payload.get("username")

        if username is None:
            raise credentials_exception

        token_data = TokenData(username=username)

    except JWTError:
        raise credentials_exception

    user = mongodb_helper.get_user(token_data.username)

    if user is None:
        raise credentials_exception

    return user

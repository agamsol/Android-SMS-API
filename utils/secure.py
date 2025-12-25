import os
from jose import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not set in .env")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Hash:

    async def get_hash(content: str) -> str:

        return pwd_context.hash(content)

    async def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)


class Token:

    async def create(username: str, remember_me: bool = False):

        expire = datetime.now(timezone.utc) + (timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))

        encoded_data = {
            "username": username,
            "exp": expire if not remember_me else 0
        }

        encoded_jwt = jwt.encode(encoded_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

        return encoded_jwt

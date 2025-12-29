import os
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from models.authentication import TokenData

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

if not JWT_SECRET or JWT_SECRET == "<RANDOM_SECURE_STRING>":
    raise RuntimeError("JWT_SECRET is not set in .env")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Hash:

    @staticmethod
    async def create(content: str) -> str:
        return pwd_context.hash(content)

    @staticmethod
    async def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)


class JWToken:

    @staticmethod
    async def create(username: str, remember_me: bool = False):

        expire = datetime.now(timezone.utc) + (timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))

        encoded_data = {
            "username": username,
            "exp": expire if not remember_me else 0
        }

        encoded_jwt = jwt.encode(encoded_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

        return encoded_jwt

    @staticmethod
    async def verify(access_token: str) -> TokenData:

        try:

            payload = jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

            username: str | None = payload.get("username")

            if username is None:
                raise ValueError("Could not validate credentials")

            return TokenData(
                username=payload.get("username"),
                exp=payload.get("exp")
            )

        except JWTError:
            raise ValueError("Could not validate credentials")

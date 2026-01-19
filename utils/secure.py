import os
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from utils.logger import create_logger
from passlib.context import CryptContext
from models.authentication import TokenData
from dotenv import load_dotenv, set_key
from datetime import datetime, timedelta, timezone
from models.authentication import generate_random_password
load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "<RANDOM_SECURE_STRING>")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

log = create_logger("SECURE", logger_name="ASA_SECURE")

if JWT_SECRET == "<RANDOM_SECURE_STRING>":

    JWT_SECRET = generate_random_password(length=99)

    set_key(
        dotenv_path=".env",
        key_to_set="JWT_SECRET",
        value_to_set=JWT_SECRET
    )

    log.critical("No JWT_SECRET specified. A new secret has been generated and saved to .env. Please note this down if needed.")

if not JWT_SECRET or JWT_SECRET == "<RANDOM_SECURE_STRING>":

    log.critical("Application startup failed: JWT_SECRET is not set or remains as default placeholder.")
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

        expire_token_minutes = 5256000 if remember_me else JWT_ACCESS_TOKEN_EXPIRE_MINUTES

        expire = datetime.now(timezone.utc) + (timedelta(minutes=expire_token_minutes))

        encoded_data = {
            "username": username,
            "exp": expire
        }

        log.debug(f"Generating JWT. User: {username}, Remember Me: {remember_me}, Exp: {encoded_data['exp']}")

        encoded_jwt = jwt.encode(encoded_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

        return encoded_jwt

    @staticmethod
    async def verify(access_token: str) -> TokenData:

        try:

            payload = jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

            username: str | None = payload.get("username")

            if username is None:
                raise ValueError("Could not validate credentials")

            log.debug(f"JWT verification successful. User: {username}, Exp: {payload.get('exp')}")

            return TokenData(
                username=payload.get("username"),
                exp=payload.get("exp")
            )

        except ExpiredSignatureError:

            log.debug("JWT verification failed: Token signature has expired.")
            raise ValueError("Could not validate credentials")

        except JWTError as e:

            log.debug(f"JWT verification failed. Error: {str(e)}")
            raise ValueError("Could not validate credentials")

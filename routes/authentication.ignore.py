from datetime import datetime, timedelta, timezone
import os
import re
from typing import Annotated, Dict, Optional
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from passlib.context import CryptContext


router = APIRouter(prefix="/auth", tags=["auth"])


load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not set in .env")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class UserBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32)
    email: Optional[EmailStr] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.fullmatch(r"[a-z0-9_.-]{3,32}", v):
            raise ValueError(
                "Username must be 3-32 characters and contain only lowercase letters, "
                "digits, and . _ -"
            )
        return v


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if " " in v:
            raise ValueError("Password must not contain spaces")
        # Enforce at least one letter, one digit, one special character
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[^\w\s]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return v.strip().lower()


class UserPublic(UserBase):
    pass


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# In-memory user store for now; replace with DB integration later
_users_db: Dict[str, Dict[str, str]] = {}


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_user(username: str) -> Optional[Dict[str, str]]:
    return _users_db.get(username)


def create_user(user_in: UserCreate) -> UserPublic:
    if user_in.username in _users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    hashed_password = get_password_hash(user_in.password)
    _users_db[user_in.username] = {
        "username": user_in.username,
        "email": user_in.email or "",
        "hashed_password": hashed_password,
    }

    return UserPublic(username=user_in.username, email=user_in.email)


def authenticate_user(username: str, password: str) -> Optional[Dict[str, str]]:
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Dict[str, str]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        username: str = payload.get("sub")  # subject
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user(token_data.username or "")
    if user is None:
        raise credentials_exception
    return user


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate) -> UserPublic:
    return create_user(user_in)


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    user = authenticate_user(form_data.username.strip().lower(), form_data.password)
    if not user:
        # Generic message to avoid user enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user["username"]})
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserPublic)
async def read_current_user(
    current_user: Annotated[Dict[str, str], Depends(get_current_user)]
) -> UserPublic:
    return UserPublic(
        username=current_user["username"],
        email=current_user.get("email") or None,
    )

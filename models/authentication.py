import re
import string
import random
from typing import Annotated, Literal, Optional
from fastapi import Form, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict

MUST_BE_ADMINISTRATOR_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="You are not authorized perform this action!"
)


def generate_random_password(length=10, custom_specials=True):

    if custom_specials:
        custom_specials = "!#$%^&*()[];:<>=-?@_+|{}~"
    else:
        custom_specials = ""

    characters = string.ascii_letters + string.digits + custom_specials
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

class LoginObtainToken(BaseModel):
    username: Annotated[str, Form(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9-]+$")]
    password: Annotated[str, Form(min_length=8, max_length=128, description="Password must be at least 8 characters long and include at least one letter, one digit, and one special character.")]
    remember_me: Annotated[bool, Form()] = False


def login_obtain_token(
    username: Annotated[str, Form(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9-]+$")],
    password: Annotated[str, Form(min_length=8, max_length=128, description="Password must be at least 8 characters long and include at least one letter, one digit, and one special character.")],
    remember_me: Annotated[bool, Form()] = False
):

    return LoginObtainToken(
        username=username,
        password=password,
        remember_me=remember_me
    )

class AdditionalAccountData(BaseModel):
    administrator: bool = False
    messages_limit: int = 50
    messages_sent: int = 0
    next_plan_reset: int = 0
    token_id: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    exp: Optional[int] = None


class CreateTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    messages_limit: int = Field(ge=0)


class UpdateTokenRequest(BaseModel):
    messages_limit: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class TokenResponse(BaseModel):
    id: str
    token: str
    name: str
    messages_limit: int


class TokenStats(BaseModel):
    id: str
    name: str
    messages_limit: int
    current_usage: int
    is_active: bool
    created_at: str # datetime serialized


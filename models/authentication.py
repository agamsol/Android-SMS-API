import re
from typing import Annotated, Optional
from fastapi import Form
from pydantic import BaseModel, Field, field_validator, ConfigDict


class BaseUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str = Field(min_length=3, max_length=32)


class CreateUser(BaseUser):
    password: str = Field(min_length=8, max_length=128, description="Password must be at least 8 characters long and include at least one letter, one digit, and one special character.")

    @field_validator("password")
    @classmethod
    def validate_password(cls, passwd: str) -> str:

        if not re.search(r"[A-Za-z]", passwd):
            raise ValueError("Password must contain at least one letter")

        if not re.search(r"\d", passwd):
            raise ValueError("Password must contain at least one digit")

        if not re.search(r"[^\w\s]", passwd):
            raise ValueError("Password must contain at least one special character")
        return passwd


class AdditionalAccountData(BaseUser):
    messages_limit: int = 50
    administrator: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    exp: Optional[int] = None


class LoginObtainToken(BaseModel):
    username: Annotated[str, Form(min_length=3, max_length=32)]
    password: Annotated[str, Form(min_length=8, max_length=128, description="Password must be at least 8 characters long and include at least one letter, one digit, and one special character.")]
    remember_me: Annotated[bool, Form()] = False


class CreateUserParams(BaseModel):
    username: Annotated[str, Form(min_length=3, max_length=32)]
    password: Annotated[str, Form(min_length=8, max_length=128, description="Password must be at least 8 characters long and include at least one letter, one digit, and one special character.")]
    messages_limit: Annotated[int, Form()] = 50
    administrator: Annotated[bool, Form()] = False
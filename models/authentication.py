import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class BaseUser(BaseModel):
    username: str = Field(min_length=3, max_length=32)


class CreateUser(BaseUser):
    password: str = Field(min_length=8, max_length=128)

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


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None

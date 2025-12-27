import re
from typing import Annotated, Optional
from fastapi import Form, HTTPException, status
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
            raise HTTPException(
                detail="Password must contain at least one letter",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if not re.search(r"\d", passwd):
            raise HTTPException(
                detail="Password must contain at least one digit",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if not re.search(r"[^\w\s]", passwd):
            raise HTTPException(
                detail="Password must contain at least one special character",
                status_code=status.HTTP_400_BAD_REQUEST
            )

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


def login_obtain_token(
    username: Annotated[str, Form(min_length=3, max_length=32)],
    password: Annotated[str, Form(min_length=8, max_length=128, description="Password must be at least 8 characters long and include at least one letter, one digit, and one special character.")],
    remember_me: Annotated[bool, Form()] = False
):

    return LoginObtainToken(
        username=username,
        password=password,
        remember_me=remember_me
    )



class CreateUserParams(BaseModel):
    username: Annotated[str, Form(min_length=3, max_length=32)]
    password: Annotated[str, Form(min_length=8, max_length=128, description="Password must be at least 8 characters long and include at least one letter, one digit, and one special character.")]
    messages_limit: Annotated[int, Form()] = 50
    administrator: Annotated[bool, Form()] = False


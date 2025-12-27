import re
from typing import Annotated, Literal, Optional
from fastapi import Form, HTTPException, status
from pydantic import BaseModel, Field, field_validator, ConfigDict

MUST_BE_ADMINISTRATOR_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="You are not authorized perform this action!"
)


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
    username: Annotated[str, Field(min_length=3, max_length=32)]
    password: Annotated[str, Field(min_length=8, max_length=128, description="Password must be at least 8 characters long and include at least one letter, one digit, and one special character.")]
    messages_limit: Annotated[int, Field()] = 50
    administrator: Annotated[bool, Field()] = False


class ResetAccountPasswordRequest(CreateUser):
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password must be at least 8 characters long and include at least one letter, one digit, and one special character.",
        alias="new_password"
    )


class AccountConfirmationResponse(BaseUser):
    detail: Literal[
        "Account has been deleted",
        "Account password has been changed",
        "Message limit has been updated"
    ]


class MessageLimitUpdateResponse(AccountConfirmationResponse):
    messages_limit: int


class UpdateMessageLimitRequest(BaseUser):
    messages_limit: int = Field(50, ge=0, description="New monthly message limit for the user")

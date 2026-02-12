from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class User_Model(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9-]+$")
    hashed_password: str = Field(..., pattern=r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")
    messages_limit: int = 0
    administrator: bool = False


class APIToken_Model(BaseModel):
    id: str
    name: str
    messages_limit: int
    created_at: datetime
    is_active: bool = True


class APITokenInDB(APIToken_Model):
    token_hash: str


class Message_Model(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9-]+$")
    token_id: Optional[str] = Field(None, description="ID of the API Token used to send this message")
    message: str = ""
    sent_to: str = Field(
        ...,
        pattern=r"^\+[1-9]\d{1,14}$"
    )
    sent_time: int

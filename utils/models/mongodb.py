from datetime import datetime
from pydantic import BaseModel, Field


class User_Model(BaseModel):
    username: str = Field(..., min_length=3, max_length=10, pattern=r"^[a-zA-Z]+$")
    hashed_password: str = Field(..., pattern=r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")
    messages_limit: int = 0
    administrator: bool = False


class Message_Model(BaseModel):
    username: str = Field(..., min_length=3, max_length=10, pattern=r"^[a-zA-Z]+$")
    message: str = ""
    sent_to: str = Field(
        ...,
        pattern=r"^(972|0)5[023458]\d{7}$",
        description="Must start with 05x (10 digits) or 9725x (12 digits). Allowed providers: 0,2,3,4,5,8."
    )
    sent_time: int
    expires_at: datetime
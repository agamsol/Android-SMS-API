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
        pattern=r"^\+[1-9]\d{1,14}$"
    )
    sent_time: int

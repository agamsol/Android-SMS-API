from pydantic import BaseModel, Field
from typing import Optional


class ErrorResponse(BaseModel):
    """Standard error response model for all API errors"""
    detail: str = Field(..., description="Error message describing what went wrong")
    status_code: int = Field(..., description="HTTP status code")
    error_type: Optional[str] = Field(None, description="Type/category of the error")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "detail": "Could not validate credentials",
                    "status_code": 401,
                    "error_type": "Unauthorized"
                }
            ]
        }


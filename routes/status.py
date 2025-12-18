import os
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, status

load_dotenv()


class StatusResponseModel(BaseModel):
    version: str = Field("0.1", max_length=10)
    filesystem: Literal["nt", "posix"]
    maintenance: bool


router = APIRouter(
    prefix="/status",
    tags=["Health"]
)


@router.get(
    "/",
    response_model=StatusResponseModel,
    status_code=status.HTTP_200_OK,
    summary="Get the status of the ADB-SMS-Gateaway"
)
async def get_status():

    return StatusResponseModel(
        version=os.getenv("VERSION"),
        filesystem=os.name,
        maintenance=False
    )

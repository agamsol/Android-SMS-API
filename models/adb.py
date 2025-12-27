from typing import Annotated, Literal, Optional
from fastapi import Form, HTTPException, status
from pydantic import BaseModel
from models.authentication import BaseUser


class AdbListDevices(BaseModel):

    id: str = "DEVICE_MODEL"
    status: Literal[
        'device',
        'unauthorized',
        'offline',
        'recovery',
        'bootloader',
        'sideload',
        'authorizing',
        'connecting'
    ]


class AdbDetailResponse(BaseModel):
    detail: Literal["ADB server has been terminated"]

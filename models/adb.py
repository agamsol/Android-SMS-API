import os
from dotenv import load_dotenv
from typing import Literal, Optional
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from models.authentication import BaseUser

load_dotenv()

ADB_SHELL_EXECUTION_ROUTE_ENABLED = os.getenv("ADB_SHELL_EXECUTION_ROUTE_ENABLED", "true").lower() == "true"

ADB_PAIRING_INSTRUCTIONS = """
### Wireless ADB Pairing Setup (Using QR-Code)

_Notes:_
1. Ensure your device is on the same Wi-Fi network.
2. Enable **Developer Options** (Settings > About Phone > Tap 'Build Number' 7 times).

**Step-by-step instructions:**
1. Go to **Settings** > **Developer Options**.
2. Enable **Wireless debugging** and tap the text to open the menu.
3. Tap **Pair device with QR code**.
4. Execute this endpoint to generate the QR code, then scan it.
5. Confirm successful pairing by checking this terminal's logs or calling the **GET** `/adb/list-devices` endpoint.

__The QR code is valid for 5 minutes__
"""


def execution_route_enabled():

    if not ADB_SHELL_EXECUTION_ROUTE_ENABLED:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature is currently disabled in the server configuration."
        )

    return


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
    detail: Literal[
        "ADB server has been terminated",
        "ADB is now connected to device",
        "ADB Error while connecting to device!",
        "Message has been successfully sent"
    ]


class AdbConnectDeviceRequest(BaseModel):
    device_id: str = Field(..., min_length=4, max_length=35)


class AdbConnectDeviceResponse(AdbConnectDeviceRequest, AdbDetailResponse):
    adb_output: str = Field(..., max_length=99)


class AdbSendTextMessageRequest(BaseModel):
    device_id: Optional[str] = Field(None, min_length=4, max_length=35, description="The unique identifier (serial) of the Android device. If omitted, a random available device will be selected.", examples=[None])
    phone_number: str = Field(
        ...,
        pattern=r"^(972|0)5[023458]\d{7}$",
        description="Must start with 05x (10 digits) or 9725x (12 digits). Allowed providers: 0,2,3,4,5,8."
    )
    message: str


class AdbMessageSentResponse(BaseUser, AdbDetailResponse, AdbConnectDeviceRequest):
    messages_sent: int
    message_content: str


class AdbShellExecuteRequest(AdbConnectDeviceRequest):
    select_device: bool = True
    command: list[str] = ['shell', 'ping', '-c', '1', '8.8.8.8']
    adb_timeout: int = 10


class AdbProcessResult(BaseModel):
    """Model representing the result of an ADB command execution"""
    args: list[str] = Field(..., description="The command that was executed")
    returncode: int = Field(..., description="Exit status of the process (0 usually means success)")
    stdout: str = Field(..., description="Standard output from the command")
    stderr: str = Field(..., description="Standard error from the command")

import os
import time
from typing import Annotated
from dotenv import load_dotenv
from utils.database import SQLiteDb
from fastapi.responses import StreamingResponse
from utils.models.database import Message_Model
from utils.adb_wireless import start_image_pairing_session
from fastapi import Depends, HTTPException, status, APIRouter
from utils.adb import Adb, DeviceUnavailable, DeviceConnectionError
from routes.authentication import authenticate_with_token, AdditionalAccountData, MUST_BE_ADMINISTRATOR_EXCEPTION
from models.adb import AdbListDevices, AdbDetailResponse, AdbConnectDeviceRequest, AdbConnectDeviceResponse, AdbSendTextMessageRequest, AdbMessageSentResponse, AdbShellExecuteRequest, AdbProcessResult, execution_route_enabled, ADB_PAIRING_INSTRUCTIONS

load_dotenv()

ADB_PATH = os.path.join("src", "bin", "adb.exe" if os.name == 'win' else 'adb')
ADB_DISABLE_SHELL_EXECUTION_ROUTE_ENABLED = os.getenv("ADB_DISABLE_SHELL_EXECUTION_ROUTE_ENABLED", "false").lower() == "true"

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/Android-SMS-API.db")
db_helper = SQLiteDb(database_path=DATABASE_PATH)
database = db_helper.connect()

adb = Adb(ADB_PATH)

router = APIRouter(
    tags=["Android Debug Bridge"]
)


@router.get(
    "/list-devices",
    status_code=status.HTTP_200_OK,
    summary="Lists all of the available android debug bridge devices and their status",
    response_model=list[AdbListDevices]
)
async def adb_list_devices(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):

    if not account.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    devices_list = await adb.get_devices()

    return devices_list


@router.get(
    "/pair-device",
    summary="Pairing a new Android device over the network via QR code",
    status_code=status.HTTP_200_OK,
    response_class=StreamingResponse,
    description=ADB_PAIRING_INSTRUCTIONS,
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "QR Code for device pairing"
        }
    }
)
async def adb_pair_device(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
) -> StreamingResponse:

    if not account.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    listener, image_bytes = start_image_pairing_session(timeout=300)

    return StreamingResponse(image_bytes, media_type="image/png")


@router.post(
    "/kill-server",
    summary="Kills the ADB server process",
    status_code=status.HTTP_200_OK,
    response_model=AdbDetailResponse
)
async def adb_kill_server(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):

    if not account.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    await adb.kill_server()

    return AdbDetailResponse(
        detail="ADB server has been terminated"
    )


@router.post(
    "/connect-device",
    summary="Connect to an Android device over the network via TCP/IP",
    status_code=status.HTTP_200_OK,
    response_model=AdbConnectDeviceResponse
)
async def adb_connect_device(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    body: AdbConnectDeviceRequest
):

    if not account.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    response_detail = "ADB Error while connecting to device!"

    device = await adb.connect_device(body.device_id)

    if "connected" in device.stdout or "already" in device.stdout:

        response_detail = "ADB is now connected to device"

    return AdbConnectDeviceResponse(
        detail=response_detail,
        device_id=body.device_id,
        adb_output=device.stdout
    )


@router.post(
    "/send-text-message",
    summary="Send an SMS message through a connected Android device",
    status_code=status.HTTP_201_CREATED,
    response_model=AdbMessageSentResponse
)
async def adb_send_text_message(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    body: AdbSendTextMessageRequest
):

    messages_sent = 0

    messages_sent = db_helper.count_messages(account.username)

    if not account.administrator:

        if messages_sent >= account.messages_limit:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have reached your monthly message limit"
            )

    try:

        parcel_sent, device_name = await adb.send_text_message(
            phone_number=body.phone_number,
            message=body.message,
            device_name=body.device_id
        )

        if parcel_sent:

            message_payload = Message_Model(
                username=account.username,
                message=body.message,
                sent_to=body.phone_number,
                sent_time=int(time.time()),
            )

            db_helper.insert_message(message_payload)

            return AdbMessageSentResponse(
                detail="Message has been successfully sent",
                username=account.username,
                messages_sent=messages_sent,
                message_content=body.message,
                device_id=device_name
            )

        raise DeviceConnectionError("Operation failed. This ADB command appears to be incompatible with your device's Android version.")

    except (DeviceUnavailable, DeviceConnectionError) as e:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    except FileNotFoundError:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADB path specified was not found!"
        )


@router.post(
    "/shell-execute",
    summary="Execute a custom shell command on a specific device",
    status_code=status.HTTP_200_OK,
    response_model=AdbProcessResult,
    dependencies=[Depends(execution_route_enabled)]
)
async def adb_shell_execute(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    body: AdbShellExecuteRequest
):

    if not account.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    if body.select_device:
        body.command = ['-s', body.device_id] + body.command

    try:

        process = await adb.adb_execute(
            command=body.command,
            timeout=body.adb_timeout
        )

        return AdbProcessResult(
            args=process.args,
            returncode=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr
        )

    except FileNotFoundError:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADB path specified was not found!"
        )

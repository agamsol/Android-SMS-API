import os
import time
import subprocess
from typing import Annotated, Optional
from dotenv import load_dotenv
from utils.database import SQLiteDb
from fastapi.responses import StreamingResponse
from utils.models.database import Message_Model
from utils.adb_wireless import start_image_pairing_session
from fastapi import Depends, HTTPException, status, APIRouter
from utils.adb import Adb, DeviceUnavailable, DeviceConnectionError
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from utils.secure import JWToken
from routes.authentication import authenticate_with_token, AdditionalAccountData, MUST_BE_ADMINISTRATOR_EXCEPTION
from collections import defaultdict
from models.adb import AdbListDevices, AdbDetailResponse, AdbConnectDeviceRequest, AdbConnectDeviceResponse, AdbSendTextMessageRequest, AdbMessageSentResponse, AdbShellExecuteRequest, AdbProcessResult, AdbPairDeviceWithCodeRequest, execution_route_enabled, ADB_QR_PAIRING_INSTRUCTIONS, ADB_PAIRING_INSTRUCTIONS, AdbMessage, AdbConversation, AdbListMessagesResponse
from utils.scheduler import get_billing_cycle_start

load_dotenv()

ADB_PATH = os.path.join("adb")
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

    devices_list = await adb.get_devices()

    return devices_list


@router.get(
    "/list-messages",
    summary="List all SMS messages from a connected device and application database",
    status_code=status.HTTP_200_OK,
    response_model=AdbListMessagesResponse
)
async def adb_list_messages(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    device_id: Optional[str] = None
):

    if not account.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    device_messages = await adb.list_messages(device_id=device_id)

    db_rows = await db_helper.get_all_messages()
    grouped = defaultdict(list)

    for row in db_rows:
        grouped[row["sent_to"]].append({
            "id": f"db-{row['sent_time']}",
            "address": row["sent_to"],
            "body": row["message"],
            "date": row["sent_time"] * 1000,
            "type": "sent"
        })

    database_messages = [
        {"phone_number": phone, "messages": msgs}
        for phone, msgs in grouped.items()
    ]

    return {
        "device_messages": device_messages,
        "database_messages": database_messages
    }


@router.get(
    "/qr-pair-device",
    summary="Pairing a new Android device over the network via QR code",
    status_code=status.HTTP_200_OK,
    response_class=StreamingResponse,
    description=ADB_QR_PAIRING_INSTRUCTIONS,
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "QR Code for device pairing"
        }
    }
)
async def adb_qr_pair_device(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
) -> StreamingResponse:

    if not account.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    listener, image_bytes = start_image_pairing_session(timeout=300)

    return StreamingResponse(image_bytes, media_type="image/png")


@router.post(
    "/pair-device",
    summary="Pairing a new Android device over the network via Pairing Code",
    status_code=status.HTTP_200_OK,
    response_model=AdbConnectDeviceResponse,
    description=ADB_PAIRING_INSTRUCTIONS
)
async def adb_code_pair_device(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)],
    body: AdbPairDeviceWithCodeRequest
):

    if not account.administrator:
        raise MUST_BE_ADMINISTRATOR_EXCEPTION

    process = await adb.code_pair_device(
        device_address=str(body.address),
        port=body.port,
        pair_code=body.pair_code
    )

    return AdbConnectDeviceResponse(
        detail="Device has been successfully paired",
        device_id=f"{body.address}:{body.port}",
        adb_output=str(process.stdout)
    )


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

    try:
        device = await adb.connect_device(body.device_id)

        if "connected" in device.stdout or "already" in device.stdout:

            response_detail = "ADB is now connected to device"

        return AdbConnectDeviceResponse(
            detail=response_detail,
            device_id=body.device_id,
            adb_output=device.stdout
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The connection attempt to the device timed out."
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

    if account.token_id:
        messages_sent = await db_helper.count_token_messages(account.token_id, since_timestamp=get_billing_cycle_start())
        if not account.messages_limit == 0 and messages_sent >= account.messages_limit:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Monthly limit exceeded")
    else:
        messages_sent = await db_helper.count_messages(account.username, since_timestamp=get_billing_cycle_start())

    try:

        parcel_sent, device_name = await adb.send_text_message(
            phone_number=body.phone_number,
            message=body.message,
            device_name=body.device_id
        )

        if parcel_sent:

            message_payload = Message_Model(
                message=body.message,
                sent_to=body.phone_number,
                sent_time=int(time.time()),
                token_id=account.token_id
            )

            await db_helper.insert_message(message_payload)

            return AdbMessageSentResponse(
                detail="Message has been successfully sent",
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

import os
from dotenv import load_dotenv
from typing import Annotated, Literal
from fastapi import Depends, HTTPException, status, APIRouter
from routes.authentication import authenticate_with_token, AdditionalAccountData
from models.adb import AdbListDevices, AdbDetailResponse
from utils.adb import Adb
from utils.mongodb import MongoDb

router = APIRouter(
    tags=["Android Debug Bridge"]
)

ADB_PATH = os.path.join("src", "bin", "adb.exe" if os.name == 'win' else 'adb')

adb = Adb(ADB_PATH)

load_dotenv()

mongodb_helper = MongoDb(
    database_name=os.getenv("MONGODB_DATABASE_NAME")
)

mongodb = mongodb_helper.connect(
    host=os.getenv("MONGODB_HOST"),
    port=int(os.getenv("MONGODB_PORT")),
    username=os.getenv("MONGODB_USERNAME"),
    password=os.getenv("MONGODB_PASSWORD")
)


@router.get(
    "/list-devices",
    summary="Lists all of the available android debug bridge devices and their status",
    response_model=list[AdbListDevices]
)
async def list_devices(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):

    devices_list = await adb.get_devices()

    return devices_list


@router.post(
    "/kill-server",
    summary="Kills the ADB server process",
    response_model=AdbDetailResponse
)
async def kill_adb_server(
    account: Annotated[AdditionalAccountData, Depends(authenticate_with_token)]
):

    await adb.kill_server()

    return AdbDetailResponse(
        detail="ADB server has been terminated"
    )

# ✅ list-devices

# ✅ kill-server

# connect-device

# send-text-message

# execute (more security option)

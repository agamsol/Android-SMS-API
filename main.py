import os
import asyncio
from dotenv import load_dotenv
from utils.adb import Adb

load_dotenv()


async def main():

    adb_path = os.path.join(
        "src",
        "bin",
        "adb.exe" if os.name == 'win' else 'adb'
    )

    adb = Adb(
        adb_path=adb_path
    )

    devices = await adb.get_devices()
    print(devices)

    parcel = await adb.send_text_message(
        phone_number=os.getenv("PHONE_NUMBER"),
        message="This is a test message from\nAndorid-SMS-API",
        device_name="192.168.1.147:5555"
    )

    print(parcel)
    return


if __name__ == "__main__":

    asyncio.run(main())

import os
import asyncio
from pydantic import IPvAnyAddress
import subprocess


class Adb:

    def __init__(self, adb_path: str):
        self.adb_path: str = self.verify_adb_path(adb_path)
        self.adb_port: int = 5555

    @staticmethod
    def verify_adb_path(adb_path=None):
        """Verify that the ADB specified exists

        Args:
            path (str, optional): Path to the adb utility. Defaults to None.

        Raises:
            FileNotFoundError: ADB Path not found
        """

        if not os.path.exists(adb_path):
            raise FileNotFoundError("ADB Initiation Failed: Library path specified was not found!")

        return adb_path

    async def adb_execute(self, command: list[str], requires_device=False):

        if requires_device:
            pass

        try:

            process = subprocess.run(
                [self.adb_path] + command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10
            )

        except FileNotFoundError:

            raise FileNotFoundError("ADB path specified was not found!")

        return process

    async def devices(self):

        adb_command = ["devices"]

        output = await self.adb_execute(adb_command)

        devices = []

        for line in output.stdout.strip().split('\n')[1:]:
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = parts[1]
                    devices.append({"id": device_id, "status": status})

        for device in devices:

            match device['status']:

                case "unauthorized":
                    pass  # Send notification to fallback webhook?

                case "offline":
                    pass  # Send notification to fallback webhook?

                case "device":
                    pass

        return devices

    async def connect_device(self, device_address: IPvAnyAddress = None):

        await self.adb_execute(
            ['tcpip', str(self.adb_port)]
        )

        process = await self.adb_execute(
            ['connect', str(device_address)]
        )

        return process

    async def kill_server(self) -> None:

        adb_command = ['kill-server']

        await self.adb_execute(adb_command)

        return

    async def send_text_message(self, phone_number: str, message: str, device=None) -> str:

        if not device:

            devices = await self.devices()

            for device in devices:

                if device['status'] == "device":

                    device = device['id']

        print(f"device: {device}")

        adb_command = [
            "-s", device,
            "shell", "service", "call", "isms", "5",
            "i32", "0",
            "s16", "com.android.mms.service",
            "s16", "null",
            "s16", phone_number,
            "s16", "null",
            f's16 "{message}"',
            "s16", "null",
            "s16", "null",
            "i32", "0",
            "i64", "0"
        ]

        parcel = await self.adb_execute(
            command=adb_command,
            requires_device=True
        )

        return parcel.stdout


async def main():

    adb_path = os.path.join(
        "src",
        "bin",
        "adb.exe" if os.name == 'win' else 'adb'
    )

    adb = Adb(
        adb_path=adb_path
    )

    devices = await adb.devices()
    print(devices)

    parcel = await adb.send_text_message("972539309365", "This is a test message from\nAndorid-SMS-API")

    print(parcel)

    return


if __name__ == "__main__":

    asyncio.run(main())

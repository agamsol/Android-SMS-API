import os
import subprocess
from pydantic import IPvAnyAddress


class DeviceConnectionError(Exception):
    """Raised when no ADB device is connected."""
    pass


class DeviceUnavailable(Exception):
    """Raised when ADB device is offline or not authorized (Allow debugging not accepted)"""
    pass


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

    async def adb_execute(self, command: list[str], timeout=10):

        try:

            process = subprocess.run(
                [self.adb_path] + command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout
            )

        except FileNotFoundError:

            raise FileNotFoundError("ADB path specified was not found!")

        return process

    async def get_devices(self):

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

    async def send_text_message(self, phone_number: str, message: str, device_name: str) -> bool:

        if not phone_number and message:
            raise ValueError("One or more required parameters were not specified!")

        device_found = False
        all_devices = await self.get_devices()

        for _ in all_devices:

            if _['id'] == device_name:

                if _["status"] != "device":

                    raise DeviceUnavailable(f"This device is not authorized\nStatus: {_['status']}")

                device_found = True

        if not device_found:
            raise DeviceConnectionError("No Authorized android device found. Please connect via USB or TCP")

        adb_command = [
            "-s", str(device_name),
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
            command=adb_command
        )

        print(parcel.stdout)

        if "Result: Parcel(00000000    '....')" == parcel.stdout:
            return False

        return True

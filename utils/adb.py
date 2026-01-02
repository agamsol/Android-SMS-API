import os
import re
import subprocess
from typing import Optional
from pydantic import IPvAnyAddress
from utils.logger import create_logger

log = create_logger("ADB", logger_name="ASA_ADB")


class DeviceConnectionError(Exception):
    """Raised when no ADB device is connected."""
    pass


class DeviceUnavailable(Exception):
    """Raised when ADB device is offline or not authorized (Allow debugging not accepted)"""
    pass


class Adb:

    def __init__(self, adb_path: str):
        self.adb_path: str = self.verify_adb_path(adb_path)

    @staticmethod
    def verify_adb_path(adb_path=None):
        """Verify that the ADB specified exists

        Args:
            path (str, optional): Path to the adb utility. Defaults to None.

        Raises:
            FileNotFoundError: ADB Path not found
        """

        if not os.path.exists(adb_path):
            log.critical(f"ADB executable missing at path: {adb_path}")
            raise FileNotFoundError("ADB Initiation Failed: Library path specified was not found!")

        return adb_path

    async def adb_execute(self, command: list[str], timeout=10):

        log.debug(f"Executing ADB command: {' '.join(command)}")

        try:

            process = subprocess.run(
                [self.adb_path] + command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout
            )

            if process.returncode != 0:
                log.warning(f"ADB command failed. Cmd: {' '.join(command)}, Return Code: {process.returncode}, Stderr: {process.stderr.strip()}")
            else:
                log.debug(f"ADB command successful. Cmd: {' '.join(command)}")

        except FileNotFoundError:
            log.critical(f"ADB execution failed: Executable not found at {self.adb_path}")
            raise FileNotFoundError("ADB path specified was not found!")

        return process

    async def get_devices(self):

        log.debug("Fetching connected ADB devices.")
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

        if not devices:
            log.info("No ADB devices currently connected.")

        for device in devices:

            match device['status']:

                case "unauthorized":
                    log.warning(f"Device found but unauthorized: {device['id']}. Check device prompt.")
                    pass  # Send notification to fallback webhook?

                case "offline":
                    log.warning(f"Device found but offline: {device['id']}.")
                    pass  # Send notification to fallback webhook?

                case "device":
                    log.debug(f"Active device ready: {device['id']}")
                    pass

        return devices

    async def pair_device(self, address: IPvAnyAddress, port: int, password: str) -> bool:

        full_address = str(address) + ":" + str(port)
        log.info(f"Attempting to pair with device at: {full_address}")

        try:

            process = await self.adb_execute(
                ['pair', full_address, password]
            )

            if "Successfully paired" in process.stdout:
                log.info(f"Pairing successful with {full_address}")
            else:
                log.warning(f"Pairing response unexpected: {process.stdout.strip()}")

            return process

        except subprocess.TimeoutExpired:
            log.error(f"Pairing timeout expired for {full_address}")

        return

    async def connect_device(self, device_address: IPvAnyAddress = None, adb_port: int = 5555, disable_tcpip_command=False):

        if not disable_tcpip_command:

            log.debug(f"Restarting ADB in TCP/IP mode on port {adb_port}")

            await self.adb_execute(
                ['tcpip', str(adb_port)]
            )

        log.info(f"Connecting to device via network: {device_address}")

        process = await self.adb_execute(
            ['connect', str(device_address)]
        )

        if "connected" in process.stdout or "already" in process.stdout:
            log.info(f"Successfully connected to {device_address}")

        else:

            log.error(f"Connection attempt failed for {device_address}. Output: {process.stdout.strip()}")

        return process

    async def kill_server(self) -> None:

        log.warning("Killing ADB server.")
        adb_command = ['kill-server']

        await self.adb_execute(adb_command)

        return

    async def send_text_message(self, phone_number: str, message: str, device_name:  Optional[str]) -> tuple:

        log.info(f"Preparing to send SMS. Recipient: {phone_number}")

        if not phone_number and message:
            log.error("SMS failed: Missing phone number or message content.")
            raise ValueError("One or more required parameters were not specified!")

        device_found = False
        all_devices = await self.get_devices()

        for _ in all_devices:

            if not device_name and _['status'] == "device":  # Choose as a default device
                device_name = _['id']
                log.debug(f"No device specified. Defaulting to first available: {device_name}")

            if _['id'] == device_name:

                if _['status'] != "device":
                    log.error(f"Target device unavailable. Device: {device_name}, Status: {_['status']}")
                    raise DeviceUnavailable(f"This device is not authorized\nStatus: {_['status']}")

                device_found = True

        if not device_found:
            log.error("SMS failed: No valid ADB devices found.")
            raise DeviceConnectionError("No Authorized android device found. Please connect via USB or TCP")

        log.debug(f"Sending SMS via device: {device_name}")
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

        if re.search(r"Result: Parcel\([0-9a-fA-F]+\s+'.*'\)", str(parcel.stdout)):
            log.info(f"SMS command executed successfully via {device_name}.")
            return True, str(device_name)

        log.error(f"SMS command failed. Device: {device_name}, Output: {parcel.stdout.strip()}")
        return False, str(device_name)

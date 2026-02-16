import os
import re
import shlex
import shutil
import asyncio
import subprocess
from fastapi import HTTPException, status
from typing import Optional
from collections import defaultdict
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

        abs_path = shutil.which(adb_path)

        if abs_path:
            adb_path = abs_path

        if not os.path.exists(adb_path) or not abs_path:
            log.critical(f"ADB executable missing at path: {adb_path}")
            raise FileNotFoundError("ADB Initiation Failed: Library path specified was not found!")

        return adb_path

    async def adb_execute(self, command: list[str], timeout=10):

        log.debug(f"Executing ADB command: {' '.join(command)}")

        try:

            process = await asyncio.create_subprocess_exec(
                self.adb_path, *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout_result, stderr_result = await asyncio.wait_for(process.communicate(), timeout=timeout)
            
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.communicate()
                raise subprocess.TimeoutExpired(cmd=[self.adb_path] + command, timeout=timeout)

            stdout_str = stdout_result.decode('utf-8', errors='replace') if stdout_result else ""
            stderr_str = stderr_result.decode('utf-8', errors='replace') if stderr_result else ""

            completed_process = subprocess.CompletedProcess(
                args=[self.adb_path] + command,
                returncode=process.returncode,
                stdout=stdout_str,
                stderr=stderr_str
            )

            if completed_process.returncode != 0:

                if "more than one device" in completed_process.stderr:
                    
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="More than one device connected, Please select a device and try again"
                    )

                log.warning(f"ADB command failed. Cmd: {' '.join(command)}, Return Code: {completed_process.returncode}, Stderr: {completed_process.stderr.strip()}")


            
            else:
                log.debug(f"ADB command successful. Cmd: {' '.join(command)}")
            
            return completed_process

        except FileNotFoundError:
            log.critical(f"ADB execution failed: Executable not found at {self.adb_path}")
            raise FileNotFoundError("ADB path specified was not found!")

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

    async def qr_pair_device(self, address: IPvAnyAddress, port: int, password: str) -> bool:

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

    async def code_pair_device(self, device_address: IPvAnyAddress, port: int, pair_code: str):

        log.info(f"Pairing to device via network: {device_address}")

        process = await self.adb_execute(
            ['pair', str(device_address) + ":" + str(port), str(pair_code)]
        )

        if "Successfully" in process.stdout:
            log.info(f"Successfully paired to {device_address}")

        else:

            log.error(f"Pairing attempt failed for {device_address}. Output: {process.stdout.strip()}")

        return process

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

        escaped_message = shlex.quote(message)

        adb_command = [
            "-s", str(device_name),
            "shell", "service", "call", "isms", "5",
            "i32", "0",
            "s16", "com.android.mms.service",
            "s16", "null",
            "s16", phone_number,
            "s16", "null",
            "s16", escaped_message,
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

    async def _parse_content_query_output(self, output: str) -> list[dict]:
        results = []
        row_pattern = re.compile(r"Row: \d+ (.*)")

        for line in output.strip().split('\n'):
            match = row_pattern.search(line)
            if not match:
                continue

            fields_str = match.group(1)
            parts = re.split(r', (?=\w+=)', fields_str)

            row_data = {}
            for part in parts:
                if '=' in part:
                    key, val = part.split('=', 1)
                    row_data[key.strip()] = val.strip()
            
            if row_data:
                results.append(row_data)
        
        return results

    async def list_messages(self, device_id: Optional[str] = None) -> list[dict]:

        log.debug(f"Listing messages for device: {device_id}")

        base_command = []
        if device_id:
            base_command.extend(["-s", device_id])

        # 1. Fetch SMS Fetching
        sms_command = base_command + ["shell", "content", "query", "--uri", "content://sms/", "--projection", "_id:address:body:date:type"]
        sms_process = await self.adb_execute(sms_command)
        
        grouped_messages = defaultdict(list)

        if sms_process.returncode == 0:
            sms_rows = await self._parse_content_query_output(sms_process.stdout)
            
            for row in sms_rows:
                msg_type = row.get('type', '1')
                if msg_type == '1':
                    msg_type_str = 'received'
                elif msg_type == '2':
                    msg_type_str = 'sent'
                else:
                    msg_type_str = 'unknown'

                try:
                    date_val = int(row.get('date', 0))
                except ValueError:
                    date_val = 0

                msg_entry = {
                    "type": msg_type_str,
                    "body": row.get('body', ''),
                    "date": date_val,
                    "id": row.get('_id'),
                    "address": row.get('address')
                }
                address = row.get('address', 'Unknown')
                grouped_messages[address].append(msg_entry)
        else:
             log.error(f"Failed to list SMS messages. Output: {sms_process.stderr}")

        # 2. Fetch MMS Messages
        mms_command = base_command + ["shell", "content", "query", "--uri", "content://mms/", "--projection", "_id:date:msg_box:sub:m_type"]
        mms_process = await self.adb_execute(mms_command)
        
        mms_messages = {}
        if mms_process.returncode == 0:

            mms_rows = await self._parse_content_query_output(mms_process.stdout)

            for row in mms_rows:
                m_id = row.get('_id')
                if m_id:
                    mms_messages[m_id] = {
                        "id": m_id,
                        "date": int(row.get('date', 0)) * 1000,
                        "msg_box": row.get('msg_box'),
                        "sub": row.get('sub', ''),
                        "body": "",
                        "address": "Unknown",
                        "type": "unknown"
                    }

        # 3. Fetch MMS Parts (For Body)
        part_command = base_command + ["shell", "content", "query", "--uri", "content://mms/part", "--projection", "mid:ct:text"]
        part_process = await self.adb_execute(part_command)

        if part_process.returncode == 0:
            part_rows = await self._parse_content_query_output(part_process.stdout)
            for row in part_rows:
                mid = row.get('mid')
                ct = row.get('ct')
                text = row.get('text')
                
                if mid in mms_messages and ct == "text/plain" and text:
                    mms_messages[mid]["body"] = text

        # 4. Fetch MMS Addresses (For Sender/Receiver)
        # type=137 (From), type=151 (To)
        addr_command = base_command + ["shell", "content", "query", "--uri", "content://mms/addr", "--projection", "msg_id:address:type"]
        addr_process = await self.adb_execute(addr_command)

        if addr_process.returncode == 0:
            addr_rows = await self._parse_content_query_output(addr_process.stdout)
            for row in addr_rows:
                msg_id = row.get('msg_id')
                address = row.get('address')
                addr_type = row.get('type')

                if msg_id in mms_messages and address:
                    if "insert-address-token" in address:
                        continue
                        
                    curr_msg = mms_messages[msg_id]

                    if curr_msg['msg_box'] == '1':
                        curr_msg['type'] = 'received'

                        if addr_type == '137':
                            curr_msg['address'] = address

                    elif curr_msg['msg_box'] == '2':
                        
                        curr_msg['type'] = 'sent'
                        
                        if addr_type == '151':
                            curr_msg['address'] = address
        
        for msg in mms_messages.values():

            if not msg['body'] and msg['sub']:
                msg['body'] = f"[MMS] {msg['sub']}"

            elif not msg['body']:
                msg['body'] = "[MMS Media]"

            final_msg_entry = {
                "type": msg['type'],
                "body": msg['body'],
                "date": msg['date'],
                "id": msg['id'],
                "address": msg['address']
            }

            grouped_messages[msg['address']].append(final_msg_entry)

        conversations = []
        for address, msgs in grouped_messages.items():

            msgs.sort(key=lambda x: x['date'] or 0)
            conversations.append({
                "phone_number": address,
                "messages": msgs
            })

        return conversations

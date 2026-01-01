import os
import io
import time
import random
import string
import socket
import asyncio
import threading
import subprocess
from qrcode import QRCode
from zeroconf import ServiceBrowser, Zeroconf
from utils.adb import Adb

ADB_PATH = os.path.join("src", "bin", "adb.exe" if os.name == 'win' else 'adb')
adb = Adb(ADB_PATH)


class QRPrepare:

    @staticmethod
    def generate_name(length=10):
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
        return "adb-pairing-" + suffix

    @staticmethod
    def generate_code(length=6):
        return ''.join(random.choices(string.digits, k=length))

    @staticmethod
    def generate_qr_content(name, password):
        return f"WIFI:T:ADB;S:{name};P:{password};;"

    @classmethod
    def generate_qr_code(cls):

        service_name = cls.generate_name()
        password = cls.generate_code()

        qr_data = cls.generate_qr_content(service_name, password)

        qr = QRCode()
        qr.add_data(qr_data)
        qr.make(fit=True)

        return service_name, password, qr


class AdbListener:

    def __init__(self, target_name, password):
        self.target_name = target_name
        self.password = password
        self.shutdown_event = threading.Event()

    def pair_device_successful(self, address, port, password) -> bool:

        process: subprocess.CompletedProcess = asyncio.run(
            adb.pair_device(address, port, password)
        )

        if process.returncode == 0 and "Successfully paired" in process.stdout:
            return True

        return False

    def connect_device_successful(self, address) -> bool:

        process: subprocess.CompletedProcess = asyncio.run(
            adb.connect_device(address, disable_tcpip_command=False)
        )

        if "connected" in process.stdout or "already" in process.stdout:
            return True

        return False

    def update_service(self, zeroconf: Zeroconf, type, name):
        pass

    def remove_service(self, zeroconf: Zeroconf, type, name):
        pass

    def add_service(self, zeroconf: Zeroconf, type, name):

        if self.target_name in name:

            info = zeroconf.get_service_info(type, name)

            if info:

                address = socket.inet_ntoa(info.addresses[0])

                if self.pair_device_successful(address, info.port, self.password):

                    self.connect_device_successful(address)

                    self.shutdown_event.set()

    def listen_for_connection(self, timeout=180):

        zeroconf = Zeroconf()

        ServiceBrowser(zeroconf, "_adb-tls-pairing._tcp.local.", self)

        start_time = time.time()

        try:

            while not self.shutdown_event.is_set():

                if time.time() - start_time > timeout:

                    print(f"[QR] Pairing session timed out ({timeout}s). The QR code is no longer valid.")

                    break

                time.sleep(0.5)

        except KeyboardInterrupt:
            pass

        finally:

            zeroconf.close()


def start_terminal_pairing_session(timeout=180):

    service_name, password, qr = QRPrepare.generate_qr_code()

    qr.print_ascii(invert=True)

    print("\nScan this QR code (Settings > Developer Options > Wireless Debugging):")

    listener = AdbListener(service_name, password)

    t = threading.Thread(
        target=listener.listen_for_connection,
        args=[timeout],
        daemon=True
    )
    t.start()

    return listener


def start_image_pairing_session(timeout=180):

    service_name, password, qr = QRPrepare.generate_qr_code()

    image = qr.make_image(fill_color="black", back_color="white")
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='PNG')
    image_bytes.seek(0)

    listener = AdbListener(service_name, password)

    t = threading.Thread(
        target=listener.listen_for_connection,
        args=[timeout],
        daemon=True
    )
    t.start()

    return listener, image_bytes

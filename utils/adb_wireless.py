import os
import time
import random
import string
import socket
import asyncio
import threading
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

    def update_service(self, zeroconf: Zeroconf, type, name):
        pass

    def remove_service(self, zeroconf: Zeroconf, type, name):
        pass

    def add_service(self, zeroconf: Zeroconf, type, name):

        if self.target_name in name:

            info = zeroconf.get_service_info(type, name)

            if info:

                address = socket.inet_ntoa(info.addresses[0])

                success = asyncio.run(
                    adb.pair_device(address, info.port, self.password)
                )

                if success:

                    print("ADB Connection Status: ADB is now connected to device")

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


if __name__ == "__main__":

    # Example

    service_name, password, qr = QRPrepare.generate_qr_code()
    qr.print_ascii(invert=True)

    listener = AdbListener(service_name, password)

    t = threading.Thread(
        target=listener.listen_for_connection,
        args=[180]
    )

    time.sleep(10000000)

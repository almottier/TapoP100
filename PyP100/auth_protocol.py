import hashlib
import logging
import os
import time
import uuid
from base64 import b64encode, b64decode

import requests
from Crypto.Hash import SHA256, SHA1
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Cipher import AES, PKCS1_v1_5
import json
import tempfile


log = logging.getLogger(__name__)


def sha1(data: bytes) -> bytes:
    return SHA1.new(data).digest()


def sha256(data: bytes) -> bytes:
    return SHA256.new(data).digest()


class AuthProtocol:
    def __init__(self, address: str, username: str, password: str):
        self.session = requests.Session()  # single session, stores cookie
        self.address = address
        self.username = username
        self.password = password
        self.key = None
        self.iv = None
        self.seq = None
        self.sig = None

    def calc_auth_hash(self, username: str, password: str) -> bytes:
        return sha256(sha1(username.encode()) + sha1(password.encode()))

    def _request_raw(self, path: str, data: bytes, params: dict = None):
        url = f"http://{self.address}/app/{path}"
        resp = self.session.post(url, data=data, timeout=2, params=params)
        resp.raise_for_status()
        data = resp.content
        return data

    def _request(self, method: str, params: dict = None):
        if not self.key:
            self.Initialize()
        payload = {"method": method}
        if params:
            # P105 requires terminalUUID in payload
            if "terminalUUID" in params.keys():
                payload["terminalUUID"] = params["terminalUUID"]
                del params["terminalUUID"]
            payload["params"] = params
        log.debug(f"Request: {payload}")
        # Encrypt payload and execute call
        encrypted = self._encrypt(json.dumps(payload).encode("UTF-8"))
        result = self._request_raw("request", encrypted, params={"seq": self.seq})
        # Unwrap and decrypt result
        data = json.loads(self._decrypt(result).decode("UTF-8"))
        # Check error code and get result
        if data["error_code"] != 0:
            log.error(f"Error: {data}")
            self.key = None
            raise Exception(f"Error code: {data['error_code']}")
        result = data.get("result")
        log.debug(f"Response: {result}")
        return result

    def _encrypt(self, data: bytes):
        self.seq += 1
        seq = self.seq.to_bytes(4, "big", signed=True)
        # Add PKCS#7 padding
        pad_l = 16 - (len(data) % 16)
        data = data + bytes([pad_l] * pad_l)
        # Encrypt data with key
        crypto = AES.new(self.key, AES.MODE_CBC, self.iv + seq)
        ciphertext = crypto.encrypt(data)
        # Signature
        sig = sha256(self.sig + seq + ciphertext)
        return sig + ciphertext

    def _decrypt(self, data: bytes):
        # Decrypt data with key
        seq = self.seq.to_bytes(4, "big", signed=True)
        crypto = AES.new(self.key, AES.MODE_CBC, self.iv + seq)
        data = crypto.decrypt(data[32:])

        # Remove PKCS#7 padding
        data = data[: -data[-1]]
        return data

    def Initialize(self):
        local_seed = get_random_bytes(16)
        response = self._request_raw("handshake1", local_seed)
        remote_seed, server_hash = response[0:16], response[16:]
        auth_hash = None
        for creds in [
            (self.username, self.password),
            ("", ""),
            ("kasa@tp-link.net", "kasaSetup"),
        ]:
            ah = self.calc_auth_hash(*creds)
            local_seed_auth_hash = sha256(local_seed + remote_seed + ah)
            if local_seed_auth_hash == server_hash:
                auth_hash = ah
                log.debug(f"Authenticated with {creds[0]}")
                break
        if not auth_hash:
            raise Exception("Failed to authenticate")
        self._request_raw("handshake2", sha256(remote_seed + local_seed + auth_hash))
        self.key = sha256(b"lsk" + local_seed + remote_seed + auth_hash)[:16]
        ivseq = sha256(b"iv" + local_seed + remote_seed + auth_hash)
        self.iv = ivseq[:12]
        self.seq = int.from_bytes(ivseq[-4:], "big", signed=True)
        self.sig = sha256(b"ldk" + local_seed + remote_seed + auth_hash)[:28]
        log.debug(f"Initialized")


class OldProtocol:
    def __init__(
        self,
        address: str,
        username: str,
        password: str,
        keypair_file: str = os.path.join(tempfile.gettempdir(), "tapo.key"),
    ):
        self.session = requests.Session()  # single session, stores cookie
        self.terminal_uuid = str(uuid.uuid4())
        self.address = address
        self.username = username
        self.password = password
        self.keypair_file = keypair_file
        self._create_keypair()
        self.key = None
        self.iv = None

    def _create_keypair(self):
        if self.keypair_file and os.path.exists(self.keypair_file):
            with open(self.keypair_file, "r") as f:
                self.keypair = RSA.importKey(f.read())
        else:
            self.keypair = RSA.generate(1024)
            if self.keypair_file:
                with open(self.keypair_file, "wb") as f:
                    f.write(self.keypair.exportKey("PEM"))

    def _request_raw(self, method: str, params: dict = None):
        # Construct url, add token if we have one
        url = f"http://{self.address}/app"
        if self.token:
            url += f"?token={self.token}"

        # Construct payload, add params if given
        payload = {
            "method": method,
            "requestTimeMils": int(round(time.time() * 1000)),
            "terminalUUID": self.terminal_uuid,
        }
        if params:
            payload["params"] = params
        log.debug(f"Request raw: {payload}")

        # Execute call
        resp = self.session.post(url, json=payload, timeout=2)
        resp.raise_for_status()
        data = resp.json()

        # Check error code and get result
        if data["error_code"] != 0:
            log.error(f"Error: {data}")
            self.key = None
            raise Exception(f"Error code: {data['error_code']}")
        result = data.get("result")

        log.debug(f"Response raw: {result}")
        return result

    def _request(self, method: str, params: dict = None):
        if not self.key:
            self.Initialize()

        # Construct payload, add params if given
        payload = {
            "method": method,
            "requestTimeMils": int(round(time.time() * 1000)),
            "terminalUUID": self.terminal_uuid,
        }
        if params:
            payload["params"] = params
        log.debug(f"Request: {payload}")

        # Encrypt payload and execute call
        encrypted = self._encrypt(json.dumps(payload))

        result = self._request_raw("securePassthrough", {"request": encrypted})

        # Unwrap and decrypt result
        data = json.loads(self._decrypt(result["response"]))
        if data["error_code"] != 0:
            log.error(f"Error: {data}")
            self.key = None
            raise Exception(f"Error code: {data['error_code']}")
        result = data.get("result")

        log.debug(f"Response: {result}")
        return result

    def _encrypt(self, data: str):
        data = data.encode("UTF-8")

        # Add PKCS#7 padding
        pad_l = 16 - (len(data) % 16)
        data = data + bytes([pad_l] * pad_l)

        # Encrypt data with key
        crypto = AES.new(self.key, AES.MODE_CBC, self.iv)
        data = crypto.encrypt(data)

        # Base64 encode
        data = b64encode(data).decode("UTF-8")
        return data

    def _decrypt(self, data: str):
        # Base64 decode data
        data = b64decode(data.encode("UTF-8"))

        # Decrypt data with key
        crypto = AES.new(self.key, AES.MODE_CBC, self.iv)
        data = crypto.decrypt(data)

        # Remove PKCS#7 padding
        data = data[: -data[-1]]
        return data.decode("UTF-8")

    def Initialize(self):
        # Unset key and token
        self.key = None
        self.token = None

        # Send public key and receive encrypted symmetric key
        public_key = self.keypair.publickey().exportKey("PEM").decode("UTF-8")
        public_key = public_key.replace("RSA PUBLIC KEY", "PUBLIC KEY")
        result = self._request_raw("handshake", {"key": public_key})
        encrypted = b64decode(result["key"].encode("UTF-8"))

        # Decrypt symmetric key
        cipher = PKCS1_v1_5.new(self.keypair)
        decrypted = cipher.decrypt(encrypted, None)
        self.key, self.iv = decrypted[:16], decrypted[16:]

        # Base64 encode password and hashed username
        digest = hashlib.sha1(self.username.encode("UTF-8")).hexdigest()
        username = b64encode(digest.encode("UTF-8")).decode("UTF-8")
        password = b64encode(self.password.encode("UTF-8")).decode("UTF-8")

        # Send login info and receive session token
        result = self._request(
            "login_device", {"username": username, "password": password}
        )
        self.token = result["token"]

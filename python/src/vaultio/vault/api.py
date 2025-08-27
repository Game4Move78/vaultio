# This file is part of vaultio.
#
# vaultio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# vaultio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with vaultio.  If not, see <https://www.gnu.org/licenses/>.

import base64
from collections import deque
import copy
from csv import Error
import datetime
import itertools
import re
import sys
import tempfile
import uuid
import json
from requests_toolbelt import MultipartEncoder
import requests
from getpass import getpass
import hashlib
import os
from rich.prompt import Prompt
from vaultio.util import ask_input, choose_input, password_input
from vaultio.vault.schema import ENCRYPTED_KEYS, INTERNAL_KEYS, make_attachment

from cryptography.hazmat.backends                   import default_backend
from cryptography.hazmat.primitives                 import ciphers, kdf, hashes, hmac, padding
from cryptography.hazmat.primitives.kdf.pbkdf2      import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf        import HKDF, HKDFExpand
from cryptography.hazmat.primitives.ciphers         import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric      import rsa, padding as asymmetricpadding
from cryptography.hazmat.primitives.serialization   import load_der_private_key
import argon2

client_name = "vaultio"
client_version = "1.13.2"
user_agent = f"{client_name}/{client_version}"

def request_prelogin(email):
    headers = {
        "content-type": "application/json",
        "accept": "*/*",
        "user-agent": user_agent,
        "bitwarden-client-name": "cli",
        "bitwarden-client-version": client_version,
        "device-type": "8",
    }
    payload = {
        "email": email
    }
    r = requests.post(
        "https://identity.bitwarden.com/api/accounts/prelogin",
        headers=headers,
        json=payload,
    )
    return r.json()

def create_derived_secrets(email, password, kdf_info):

    password = password.encode("utf-8")

    email = email.strip().lower()

    iterations = kdf_info["kdfIterations"]
    memory = kdf_info["kdfMemory"]
    parallelism = kdf_info["kdfParallelism"]
    kdf_type = kdf_info["kdf"]
    # kdf_info["kdfIterations"], kdf_info["kdfMemory"], kdf_info["kdfParallelism"], kdf_info["kdf"]

    if (kdf_type==1):
        ph = hashes.Hash(hashes.SHA256(),default_backend())
        ph.update(bytes(email, 'utf-8'))
        salt = ph.finalize()
        password_key = argon2.low_level.hash_secret_raw(
            password,
            salt,
            time_cost=iterations,
            memory_cost=memory * 1024,
            parallelism=parallelism,
            hash_len=32,
            type=argon2.low_level.Type.ID
        )
    else:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=email.encode('utf-8'),
            iterations=iterations,
            backend=default_backend(),
        )
        password_key = kdf.derive(password)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=password,
        iterations=1,
        backend=default_backend()
    )

    password_hash  = base64.b64encode(kdf.derive(password_key)).decode('utf-8')

    hkdf = HKDFExpand(
        algorithm=hashes.SHA256(),
        length=32,
        info=b"enc",
        backend=default_backend()
    )

    enc = hkdf.derive(password_key)

    hkdf = HKDFExpand(
        algorithm=hashes.SHA256(),
        length=32,
        info=b"mac",
        backend=default_backend()
    )

    mac = hkdf.derive(password_key)

    key = enc + mac

    return dict(
        password_hash=password_hash,
        enc=enc,
        mac=mac,
        key=key,
    )

def create_sync_secrets(profile):
    enc = profile["key"]
    private_key = profile["key"]
    return dict(enc=enc, private_key=private_key)

def encode_urlsafe_nopad(data: str) -> str:
    encoded = base64.urlsafe_b64encode(data.encode()).decode()
    return encoded.rstrip('=')

def hash_password_pbkdf2_stdlib(email, password, iterations):
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), email.encode(), iterations, dklen=32)
    return base64.b64encode(key).decode(), key

TWO_FACTOR = [
    {
        "provider": 0,
        "name": "Authenticator",
        "msg": "Enter the 6 digit verification code from your authenticator app."
    },
    {
        "provider": 1,
        "name": "Email",
        "msg": "Enter the PIN you received via email."
    },
    None,
    {
        "provider": 3,
        "name": "Yubikey",
        "msg": "Insert your Yubikey and push the button."
    },
]

def get_providers(resp):

    providers = resp.get("TwoFactorProviders2")

    if providers is None:
        return None

    return (
        TWO_FACTOR[int(provider)]
        for provider, info in providers.items()
    )

def choose_provider(providers, choice=None):

    providers = list(providers)
    assert len(providers) != 0
    choices = {p["name"]: p for p in providers}

    if choice is None:
        choice = choose_input("provider", list(choices.keys()))

    return choices[choice]

def request_login(email, secrets, device_id, provider=None, provider_token=None):
    base_payload = {
        "grant_type": "password",
        "scope": "api offline_access",
        "client_id": "cli",
        "deviceType": "8",
        "deviceIdentifier": device_id,
        "deviceName": user_agent,
        "devicePushToken": "",
        "username": email,
        "password": secrets["password_hash"],
    }

    if provider is not None:
        if provider_token is None:
            provider_token = ask_input(provider["name"], provider["msg"], show=True)
        base_payload["twoFactorToken"] = provider_token,
        base_payload["twoFactorProvider"] = str(provider["provider"])

    headers = {
        "user-agent": user_agent,
        "auth-email": encode_urlsafe_nopad(email),
        "bitwarden-client-name": "cli",
        "bitwarden-client-version": "1.13.2",
        "device-type": "8",
    }

    r = requests.post("https://identity.bitwarden.com/connect/token", data=base_payload, headers=headers)

    return r.json()


class AccessError(Exception):

    def __init__(self, resp) -> None:
        self.resp = resp
        if "error_description" in resp:
            super().__init__(resp["error_description"])
        else:
            super().__init__(json.dumps(resp))

def check_token(r):

    if "access_token" not in r:
        raise AccessError(r)

    return r

def request_access_token(email, secrets, device_id, provider_choice=None, provider_token=None):

    r = request_login(email, secrets, device_id)

    providers = get_providers(r)

    if providers is not None:
        provider = choose_provider(providers, provider_choice)
        request_prelogin(email)
        r = request_login(email, secrets, device_id, provider, provider_token)

    return check_token(r)

def request_refresh_token(token, device_id):
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        "scope": "api offline_access",
        "client_id": "cli",
        "deviceType": "8",
        "deviceIdentifier": device_id,
        "deviceName": user_agent,
        "devicePushToken": "",
    }
    headers = {
        "user-agent": user_agent,
        "bitwarden-client-name": "cli",
        "bitwarden-client-version": "1.13.2",
        "device-type": "8",
    }
    r = requests.post("https://identity.bitwarden.com/connect/token", data=payload, headers=headers)
    r.raise_for_status()
    return token | r.json()

def request_sync(token, device_id):

    token_type = token["token_type"]
    access_token = token["access_token"]

    headers = {
        "authorization": f"{token_type} {access_token}",
        "user-agent": user_agent,
        "bitwarden-client-name": "cli",
        "bitwarden-client-version": client_version,
        "device-type": "8",
    }

    url = "https://api.bitwarden.com/sync"

    r = requests.get(
        url,
        headers=headers
    )
    if r.status_code == 401:
        token = request_refresh_token(token, device_id)
        headers["authorization"] = authorization_header(token)
        resp = requests.delete(url, headers=headers)

    r.raise_for_status()
    return r.json(), token

CHECK_ENC_MSG = "\n".join((
    "ERROR: Unsupported EncryptionType: {enc_type}",
))

def check_enc_type(enc_type, assumed_type, msg=None):
    if int(enc_type) == int(assumed_type):
        return
    if msg is None:
        msg = CHECK_MAC_MSG
    else:
        msg = f"{CHECK_MAC_MSG} {msg}"
    msg = msg.format(enc_type=str(enc_type))
    raise Error(msg)

CHECK_MAC_MSG = "\n".join((
    "ERROR: MAC did not match. Protected Symmetric Key was not decrypted. (Password may be wrong)",
))

class MACError(Exception):

    def __init__(self, old_mac, new_mac, msg) -> None:
        self.old_mac = old_mac
        self.new_mac = new_mac
        if msg is None:
            msg = CHECK_MAC_MSG
        else:
            msg = f"{CHECK_MAC_MSG} {msg}"
        super().__init__(msg)

def check_mac(old_mac, new_mac, msg=None):
    if old_mac == new_mac:
        return
    raise MACError(old_mac, new_mac, msg)

CHECK_DECRYPT_MSG = "\n".join((
    "Wrong Password. Could Not Decode Protected Symmetric Key.",
))

def check_decrypt(unpadder, decrypted):
    try:
        return unpadder.update(decrypted) + unpadder.finalize()
    except Exception as e:
        raise Exception(CHECK_DECRYPT_MSG)

def decrypt_ciphertext2(text, secrets, iv) -> bytes:
    padder = padding.PKCS7(128).padder()
    text = padder.update(text) + padder.finalize()
    unpadder    = padding.PKCS7(128).unpadder()
    cipher      = Cipher(algorithms.AES(secrets["enc"]), modes.CBC(iv), backend=default_backend())
    decryptor   = cipher.decryptor() 
    decrypted   = decryptor.update(text) + decryptor.finalize()
    return check_decrypt(unpadder, decrypted)

def _decrypt(iv, text, mac, secrets) -> bytes:

    # Calculate ciphertext MAC
    h = hmac.HMAC(secrets["mac"], hashes.SHA256(), backend=default_backend())
    h.update(iv)
    h.update(text)
    new_mac = h.finalize()

    check_mac(mac, new_mac)

    unpadder    = padding.PKCS7(128).unpadder()
    cipher      = Cipher(algorithms.AES(secrets["enc"]), modes.CBC(iv), backend=default_backend())
    decryptor   = cipher.decryptor() 
    decrypted   = decryptor.update(text) + decryptor.finalize()

    return check_decrypt(unpadder, decrypted)

def _decrypt_stream(iv, chunks, mac, secrets):

    # Calculate ciphertext MAC
    h = hmac.HMAC(secrets["mac"], hashes.SHA256(), backend=default_backend())
    h.update(iv)

    unpadder    = padding.PKCS7(128).unpadder()
    cipher      = Cipher(algorithms.AES(secrets["enc"]), modes.CBC(iv), backend=default_backend())
    decryptor   = cipher.decryptor() 
    # decrypted   = decryptor.update(text) + decryptor.finalize()

    for chunk in chunks:
        h.update(chunk)
        chunk = decryptor.update(chunk)
        yield unpadder.update(chunk)

    new_mac = h.finalize()
    check_mac(mac, new_mac)

    chunk = decryptor.finalize()
    yield unpadder.update(chunk) + unpadder.finalize()

def decrypt_ciphertext(ciphertext, secrets) -> bytes:
    tokens = ciphertext.split(".")
    iv, text, mac = (
        base64.b64decode(x)
        for x in tokens[1].split("|")[:3]
    )

    return _decrypt(iv, text, mac, secrets)

def decrypt_blob(data, secrets) -> bytes:
    data = data[1:]
    iv, mac, text = data[:16], data[16:16+32], data[16+32:]

    return _decrypt(iv, text, mac, secrets)

def resize_chunks(it, size):
    it = iter(it)
    bfr = bytearray()
    for chunk in it:
        bfr += chunk
        while len(bfr) >= size:
            yield bytes(bfr[:size])
            bfr = bfr[size:]

    while len(bfr) >= size:
        yield bfr[:size]
        bfr = bfr[size:]

    if bfr:
        yield bytes(bfr)

def extract_chunk(chunks, size, initial=None):
    bfr = bytearray()
    if initial is not None:
        bfr += initial
    while len(bfr) < size:
        bfr += next(chunks)
    return bfr[:size], bfr[size:]

def prepend_chunk(chunks, initial):
    yield initial
    yield from chunks

def decrypt_blob_stream(chunks, secrets):
    enc_type, chunk = extract_chunk(chunks, 1)
    iv, chunk = extract_chunk(chunks, 16, chunk)
    mac, chunk = extract_chunk(chunks, 32, chunk)
    for chunk in _decrypt_stream(iv, prepend_chunk(chunks, chunk), mac, secrets):
        if chunk:
            yield chunk

def iter_file_chunks(fin, chunk_size=8192):
    while True:
        chunk = fin.read(chunk_size)
        if len(chunk) == 0:
            return
        yield chunk

def decrypt_blob_from_file(fpath, secrets, chunk_size=8192):
    with open(fpath, "rb") as fin:
        chunks = iter_file_chunks(fin)
        yield from decrypt_blob_stream(chunks, secrets)

def _encrypt(iv, text, secrets):

    padder = padding.PKCS7(128).padder()
    padded = padder.update(text) + padder.finalize()

    cipher = Cipher(
        algorithms.AES(secrets["enc"]),
        modes.CBC(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    text = encryptor.update(padded) + encryptor.finalize()

    # Compute HMAC over IV + ciphertext
    h = hmac.HMAC(secrets["mac"], hashes.SHA256(), backend=default_backend())
    h.update(iv)
    h.update(text)
    mac = h.finalize()

    return text, mac

def _encrypt_stream(iv, chunks, secrets):

    padder = padding.PKCS7(128).padder()
    # padded = padder.update(text) + padder.finalize()

    cipher = Cipher(
        algorithms.AES(secrets["enc"]),
        modes.CBC(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    # text = encryptor.update(padded) + encryptor.finalize()
    h = hmac.HMAC(secrets["mac"], hashes.SHA256(), backend=default_backend())
    h.update(iv)

    for chunk in chunks:
        padded = padder.update(chunk)
        chunk = encryptor.update(chunk)
        h.update(chunk)
        yield chunk

    chunk = padder.finalize()
    chunk = encryptor.update(chunk) + encryptor.finalize()
    h.update(chunk)
    yield chunk

    # Compute HMAC over IV + ciphertext
    mac = h.finalize()

    yield mac

def encrypt_ciphertext(text, secrets) -> str:
    iv = os.urandom(16)

    text, mac = _encrypt(iv, text, secrets)

    return "2." + "|".join((
        base64.b64encode(x).decode("utf-8")
        for x in (iv, text, mac)
    ))

def encrypt_blob(text, secrets):
    iv = os.urandom(16)

    iv, text, mac = _encrypt(iv, text, secrets)

    return b"\x02" + iv + mac + text

def encrypt_blob_to_file(chunks, secrets, fpath, chunk_size=8192):
    iv = os.urandom(16)

    chunks = _encrypt_stream(iv, chunks, secrets)

    old = next(chunks)

    with open(fpath, "wb") as fout:
        fout.write(b"\x02" + iv + bytes(32))
        for chunk in chunks:
            fout.write(old)
            old = chunk

    mac = old

    with open(fpath, "r+b") as fout:
        fout.seek(1 + 16)
        fout.write(mac)

def decrypt_rsa(ciphertext, master_enc):
    tokens = ciphertext.split(".")
    check_enc_type(tokens[0], 4)
    text = base64.b64decode(tokens[1].split("|")[0])
    private_key = load_der_private_key(master_enc, password=None, backend=default_backend())

    return private_key.decrypt(
        text,
        asymmetricpadding.OAEP(
            mgf=asymmetricpadding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None
        )
    )

def next_choice(choices):
    try:
        choice = next(choices)
        return choices, choice
    except StopIteration:
        return None
import re

def decrypt_object_key(key, secrets):
    key = decrypt_ciphertext(key, secrets)
    enc, mac = key[:32], key[32:]
    return dict(enc=enc, mac=mac)

def new_object_key(secrets):
    key = os.urandom(64)
    enc, mac = key[:32], key[32:]
    key = encrypt_ciphertext(key, secrets)
    return key, {"enc": enc, "mac": mac}

def decrypt_object(root, secrets, encrypt=False):
    stack = []
    pattern = re.compile(r"\d\.[^,]+\|[^,]+=+")
    node = root
    node_secrets = secrets
    while True:
        # print(".".join([str(key) for *_, key in stack]))
        if not isinstance(node, (dict, list)):
            # path = [key for *_, key in stack]
            encrypted = (isinstance(node, str) and pattern.match(node))
            if len(stack) == 0:
                return root
            node_secrets, parent, keys, key = stack.pop()
            # print(f"{key} = {node}")
            # if encrypted and key != "key":
            if node is not None and key in ENCRYPTED_KEYS:
                if encrypt:
                    assert isinstance(node, str)
                    node = encrypt_ciphertext(node.encode("utf-8"), node_secrets)
                else:
                    node = decrypt_ciphertext(node, node_secrets).decode("utf-8")
                parent[key] = node
            else:
                assert not encrypted or key in INTERNAL_KEYS
            try:
                key = next(keys)
                stack.append((node_secrets, parent, keys, key))
                node = parent[key]
            except StopIteration:
                node = None
        else:
            if isinstance(node, dict):
                if node.get("object") in ("cipherDetails", "cipher") and isinstance(node.get("key"), str) and pattern.match(node["key"]):
                    node_secrets = decrypt_object_key(node["key"], node_secrets)
                keys = iter(node.keys())
            else:
                keys = iter(range(len(node)))
            try:
                key = next(keys)
                stack.append((node_secrets, node, keys, key))
                node = node[key]
            except StopIteration:
                node = None

def encrypt_object(root, secrets):
    return decrypt_object(root, secrets, True)

def download_sync(email=None, password=None, provider_choice=None, provider_token=None):

    if email is None:
        email = password_input(field="email", show=True)

    if password is None:
        password = password_input()

    kdf_info = request_prelogin(email)

    device_id = str(uuid.uuid4())

    derived_secrets = create_derived_secrets(email, password, kdf_info)
    token = request_access_token(email, derived_secrets, device_id, provider_choice, provider_token)

    sync, token = request_sync(token, device_id)

    sync["ciphers"] = {
        obj["id"]: obj
        for obj in sync["ciphers"]
    }

    sync["folders"] = {
        obj["id"]: obj
        for obj in sync["folders"]
    }

    sync_secrets = create_sync_secrets(sync["profile"])

    return dict(device_id=device_id, token=token, email=email, folders=sync["folders"], ciphers=sync["ciphers"], kdf=kdf_info, secrets=sync_secrets)

def refresh_sync(sync):

    email = sync["email"]
    sync["token"] = request_refresh_token(sync["token"], sync["device_id"])

    kdf_info = dict(
        kdfIterations=sync["token"]["KdfIterations"],
        kdfMemory=sync["token"]["KdfMemory"],
        kdfParallelism=sync["token"]["KdfParallelism"],
        kdf=sync["token"]["Kdf"],
    )

    device_id = sync["device_id"]

    sync, token = request_sync(sync["token"], sync)

    sync["ciphers"] = {
        obj["id"]: obj
        for obj in sync["ciphers"]
    }

    sync["folders"] = {
        obj["id"]: obj
        for obj in sync["folders"]
    }

    sync_secrets = create_sync_secrets(sync["profile"])

    return dict(device_id=device_id, token=token, email=email, folders=sync["folders"], ciphers=sync["ciphers"], kdf=kdf_info, secrets=sync_secrets)

def create_vault_secrets(sync, password):
    derived_secrets = create_derived_secrets(sync["email"], password, sync["kdf"])
    return decrypt_object_key(sync["secrets"]["enc"], derived_secrets)

def decrypt_sync(sync, secrets):

    ciphers = decrypt_object(copy.deepcopy(sync["ciphers"]), secrets)
    folders = decrypt_object(copy.deepcopy(sync["folders"]), secrets)

    return dict(ciphers=ciphers, folders=folders)

def encrypt_sync(sync, secrets):

    ciphers = encrypt_object(copy.deepcopy(sync["ciphers"]), secrets)
    folders = encrypt_object(copy.deepcopy(sync["folders"]), secrets)

    return dict(ciphers=ciphers, folders=folders)

UPDATE_TYPES = {
    "cipher",
    "folder"
}

def authorization_header(token):
    token_type = token["token_type"]
    access_token = token["access_token"]
    return f"{token_type} {access_token}"

def update_request(sync, obj, type, new=False, delete=False, get=False):
    type = type.rstrip("s")
    if type not in UPDATE_TYPES:
        return
    headers = {
        "authorization": authorization_header(sync["token"]),
        "user-agent": user_agent,
        "bitwarden-client-name": "cli",
        "bitwarden-client-version": client_version,
        "device-type": "8",
        "Content-Type": "application/json",
    }
    if delete:
        id = obj
        url = f"https://api.bitwarden.com/{type}s/{id}"
        r = requests.delete(url, headers=headers)
        if r.status_code == 401:
            sync["token"] = request_refresh_token(sync["token"], sync["device_id"])
            headers["authorization"] = authorization_header(sync["token"])
            resp = requests.delete(url, headers=headers)
    elif new:
        url = f"https://api.bitwarden.com/{type}s"
        r = requests.post(url, headers=headers, json=obj)
        if r.status_code == 401:
            sync["token"] = request_refresh_token(sync["token"], sync["device_id"])
            headers["authorization"] = authorization_header(sync["token"])
            resp = requests.post(url, headers=headers)
    elif get:
        id = obj
        url = f"https://api.bitwarden.com/{type}s/{id}"
        r = requests.get(url, headers=headers)
        if r.status_code == 401:
            sync["token"] = request_refresh_token(sync["token"], sync["device_id"])
            headers["authorization"] = authorization_header(sync["token"])
            resp = requests.get(url, headers=headers)
    else: #put
        id = obj["id"]
        url = f"https://api.bitwarden.com/{type}s/{id}"
        r = requests.put(url, headers=headers, json=obj)
        if r.status_code == 401:
            sync["token"] = request_refresh_token(sync["token"], sync["device_id"])
            headers["authorization"] = authorization_header(sync["token"])
            resp = requests.put(url, headers=headers)
    r.raise_for_status()
    return r.json()

def request_attachment(sync, item_id, attachment_id):
    headers = {
        "authorization": authorization_header(sync["token"]),
        "user-agent": user_agent,
        "bitwarden-client-name": "cli",
        "bitwarden-client-version": client_version,
        "device-type": "8",
    }


    url = f"https://api.bitwarden.com/ciphers/{item_id}/attachment/{attachment_id}"
    r = requests.get(url, headers=headers)

    if r.status_code == 401:
        sync["token"] = request_refresh_token(sync["token"], sync["device_id"])
        headers["authorization"] = authorization_header(sync["token"])
        r = requests.get(url, headers=headers)

    r.raise_for_status()

    return r.json()

def request_attachment_new(sync, item_id, key, fname, fsize):
    headers = {
        "authorization": authorization_header(sync["token"]),
        "user-agent": user_agent,
        "bitwarden-client-name": "cli",
        "bitwarden-client-version": client_version,
        "device-type": "8",
    }

    payload = {
        "fileName": fname,
        "key": key,
        "fileSize": fsize,
        "adminRequest": False,
    }

    url = f"https://api.bitwarden.com/ciphers/{item_id}/attachment/v2"
    r = requests.post(url, headers=headers, json=payload)

    if r.status_code == 401:
        sync["token"] = request_refresh_token(sync["token"], sync["device_id"])
        headers["authorization"] = authorization_header(sync["token"])
        r = requests.post(url, headers=headers, json=payload)

    r.raise_for_status()

    return r.json()

def decrypt_file_blob_stream(path, secrets, chunk_size=8192):
    with open(path, "rb") as fin:
        chunks = iter_file_chunks(fin, chunk_size)
        yield from decrypt_blob_stream(chunks, secrets)

def decrypt_file_blob_to(src, dst, secrets, chunk_size=8192):
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        chunks = iter_file_chunks(fin, chunk_size)
        for chunk in decrypt_blob_stream(chunks, secrets):
            fout.write(chunk)

def download_attachment(sync, item_id, attachment_id, secrets=None, chunk_size=8192, decrypted=False):
    attachment = request_attachment(sync, item_id, attachment_id)
    r = requests.get(attachment["url"], stream=True)
    r.raise_for_status()
    chunks = r.iter_content(chunk_size=chunk_size)
    if decrypted:
        assert secrets is not None
        secrets = decrypt_object_key(attachment["key"], secrets)
        yield from decrypt_blob_stream(chunks, secrets)
    else:
        yield from chunks

def parse_azure_sas_params(url):
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    version = query_params.get("sv", [None])[0]
    expiry = query_params.get("se", [None])[0]
    permissions = query_params.get("sp", [None])[0]
    signature = query_params.get("sig", [None])[0]
    return {
        "version": version,
        "expiry": expiry,
        "permissions": permissions,
        "signature": signature,
    }

def encrypt_file(src, dst, secrets, chunk_size=8192):
    with open(src, "rb") as fin:
        encrypt_blob_to_file(iter_file_chunks(fin), secrets, dst, chunk_size)

def upload_attachment(sync, item_id, fpath, secrets, chunk_size=8192, encrypt=True):
    fname = os.path.basename(fpath)
    fname = encrypt_ciphertext(fname.encode("utf-8"), secrets)
    key, secrets = new_object_key(secrets)
    if encrypt:
        fpath = fpath + ".enc"
        encrypt_file(fpath, fpath, secrets, chunk_size)
    # with open(fpath, "rb") as fin:
    #     encrypt_blob_to_file(iter_file_chunks(fin), secrets, fpath, chunk_size)
    for chunk in decrypt_blob_from_file(fpath, secrets):
        print(chunk)
    fsize = os.path.getsize(fpath)
    attachment = request_attachment_new(sync, item_id, key, fname, fsize)
    params = parse_azure_sas_params(attachment["url"])
    # https://github.com/bitwarden/clients/blob/main/libs/common/src/platform/services/file-upload/azure-file-upload.service.ts#L11
    headers = {
        "x-ms-date": datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
        "x-ms-version": params["version"],
        "Content-Length": str(fsize),
        "x-ms-blob-type": "BlockBlob",
    }
    with open(fpath, "rb") as fin:
        r = requests.put(
            attachment["url"],
            data=fin,
            headers=headers
        )
    r.raise_for_status()

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
from csv import Error
import re
import sys
import uuid
import json
import requests
from getpass import getpass
import hashlib
import os
from rich.prompt import Prompt
from vaultio.util import ask_input, choose_input, password_input

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
        raise NotImplementedError
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
        base_payload["twoFactorProvider"] = str(provider["provider"]),

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

    return r["access_token"]

def request_access_token(email, secrets, device_id, provider_choice=None, provider_token=None):

    r = request_login(email, secrets, device_id)

    providers = get_providers(r)

    if providers is not None:
        provider = choose_provider(providers, provider_choice)
        request_prelogin(email)
        r = request_login(email, secrets, device_id, provider, provider_token)

    return check_token(r)

def request_sync(token):

    headers = {
        "authorization": f"Bearer {token}",
        "user-agent": user_agent,
        "bitwarden-client-name": "cli",
        "bitwarden-client-version": client_version,
        "device-type": "8",
    }

    r = requests.get(
        "https://api.bitwarden.com/sync",
        headers=headers
    )
    r.raise_for_status()
    return r.json()

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
    "Wrong Password. Could Not Decode Protected Symmetric Key."
))

def check_decrypt(unpadder, decrypted):
    try:
        return unpadder.update(decrypted) + unpadder.finalize()
    except Exception as e:
        raise Exception(CHECK_DECRYPT_MSG)

def decrypt_ciphertext(ciphertext, secrets) -> bytes:
    tokens = ciphertext.split(".")
    iv, text, mac = (
        base64.b64decode(x)
        for x in tokens[1].split("|")[:3]
    )

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

def decrypt_object(root, secrets):
    stack = []
    pattern = re.compile(r"\d\.[^,]+\|[^,]+=+")
    node = root
    node_secrets = secrets
    while True:
        # print(".".join([str(key) for *_, key in stack]))
        if not isinstance(node, (dict, list)):
            encrypted = (isinstance(node, str) and pattern.match(node))
            if len(stack) == 0:
                return root
            node_secrets, parent, keys, key = stack.pop()
            # print(f"{key} = {node}")
            if encrypted and key != "key":
                node = decrypt_ciphertext(node, node_secrets).decode("utf-8")
                parent[key] = node
            try:
                key = next(keys)
                stack.append((node_secrets, parent, keys, key))
                node = parent[key]
            except StopIteration:
                node = None
        else:
            if isinstance(node, dict):
                if node.get("object") == "cipherDetails" and isinstance(node.get("key"), str) and pattern.match(node["key"]):
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

def download_sync(email=None, password=None, provider_choice=None, provider_token=None):

    if email is None:
        email = password_input(field="email", show=True)

    if password is None:
        password = password_input()

    kdf_info = request_prelogin(email)

    device_id = str(uuid.uuid4())

    derived_secrets = create_derived_secrets(email, password, kdf_info)
    token = request_access_token(email, derived_secrets, device_id, provider_choice, provider_token)
    sync = request_sync(token)
    sync_secrets = create_sync_secrets(sync["profile"])

    return dict(email=email, folders=sync["folders"], ciphers=sync["ciphers"], kdf=kdf_info, secrets=sync_secrets), derived_secrets

def decrypt_sync(sync, derived_secrets):

    vault_secrets = decrypt_object_key(sync["secrets"]["enc"], derived_secrets)

    import copy
    ciphers = decrypt_object(copy.deepcopy(sync["ciphers"]), vault_secrets)
    folders = decrypt_object(copy.deepcopy(sync["folders"]), vault_secrets)

    return dict(ciphers=ciphers, folders=folders)

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
import json
import os
from pathlib import Path
import subprocess

import requests
from vaultio.vault.api import MACError, create_derived_secrets, create_vault_secrets, decrypt_blob, decrypt_blob_stream, decrypt_ciphertext, decrypt_object, decrypt_object_key, decrypt_sync, download_attachment, download_sync, encrypt_ciphertext, encrypt_object, encrypt_sync, new_object_key, refresh_sync, request_attachment, update_request, upload_attachment
from vaultio.util import CACHE_DIR, SYNC_CACHE, InputError, password_input
from vaultio.vault.schema import make_cipher

class VaultSync:

    def __init__(self, encrypted=None, email=None, password=None, provider_choice=None, provider_token=None, cache=SYNC_CACHE) -> None:

        if cache is not None and Path(cache).exists():
            with open(cache, "r") as fin:
                encrypted = json.load(fin)
        else:
            encrypted = None

        if encrypted is None:
            encrypted = download_sync(email, password, provider_choice, provider_token)
            if cache is not None:
                with open(cache, "w") as fout:
                    json.dump(encrypted, fout)

        self.encrypted = encrypted
        self.decrypted = None
        self.secrets = None

        self.cache = cache

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.encrypt(self.secrets)
        if self.cache is None:
            return
        with open(self.cache, "w") as fout:
            encrypted = json.dump(self.encrypted, fout)
        # self.decrypted = self.secrets = None
        pass

    def lock(self):
        self.encrypt(self.secrets)
        self.decrypted = None
        self.secrets = None
        return True

    def encrypt(self, secrets):

        if self.decrypted is None:
            return

        try:
            self.encrypted |= encrypt_sync(self.decrypted, secrets)
        except (InputError, MACError):
            return False

    def decrypt(self, secrets):

        try:
            import copy
            removed = ["3cd45930-7f43-41bf-a5b7-b2c7014054a8"]
            for item in copy.deepcopy(self.encrypted["ciphers"]).values():
                try:
                    name = decrypt_ciphertext(item["name"], secrets).decode("utf-8")
                except Exception:
                    continue
                if "vaultio" in name and item["id"] not in removed:
                    print("Removing " + item["id"])
                    assert input("Continue? ") == "y"
                    print()
                    update_request(self.encrypted, item["id"], "cipher", delete=True)
            self.decrypted = decrypt_sync(self.encrypted, secrets)
            self.secrets = secrets
            return True
        except Exception:
            raise
        # except (InputError, MACError):
        #     return False

    def unlock(self, password=None):

        if password is None:
            password = password_input()

        secrets = create_vault_secrets(self.encrypted, password)

        return self.decrypt(secrets)

    def sync(self):
        self.encrypted = refresh_sync(self.encrypted)
        if self.secrets is not None:
            self.decrypted = decrypt_sync(self.encrypted, self.secrets)
        return True

    def status(self):
        raise NotImplementedError

    def generate(
            self, length=None, uppercase=None, lowercase=None, numbers=None, special=None,
            passphrase=None, words=None, seperator=None, capitalize=None, include_number=None,
            ambiguous=None, min_number=None, min_special=None
    ):

        raise NotImplementedError

    def fingerprint(self):
        raise NotImplementedError

    def template(self, type):
        raise NotImplementedError

    def get_attachment(self, attachment_id, item_id):
        yield from download_attachment(self.encrypted, item_id, attachment_id, self.secrets)

    def new_attachment(self, item_id, fpath=None):
        return upload_attachment(self.encrypted, item_id, fpath, self.secrets)

    GET_TYPES = {
        "totp",
        "notes",
        "password",
        "username",
        "item",
        "folder",
    }

    def get(self, uuid, type="item"):
        assert type in self.GET_TYPES
        if type == "folder":
            return self.decrypted["folders"][uuid]
        else:
            item = self.decrypted["ciphers"][uuid]
            if type == "item":
                return item
            elif type == "uri":
                return item["uri"]
            elif type == "totp":
                return item["totp"]
            elif type == "notes":
                return item["secureNote"]
            elif type == "username":
                return item["login"]["username"]
            elif type == "password":
                return item["login"]["password"]

    NEW_TYPES = {
    }

    def new(self, value, type="item"):
        if type == "item":
            value = make_cipher(value)
            # value["key"], _ = new_object_key(self.secrets)
        value = encrypt_object(value, self.secrets)
        decrypt_object(value, self.secrets)
        if type == "folder":
            value = update_request(self.encrypted, value, "folder", new=True)
        elif type == "item":
            value = update_request(self.encrypted, value, "cipher", new=True)
        else:
            raise NotImplementedError
        value = decrypt_object(value, self.secrets)
        return value

    EDIT_TYPES = {
        "folder",
        "item"
    }

    def edit(self, value, type="item"):
        if type == "folder":
            value = encrypt_object(value, self.secrets)
            value = update_request(self.encrypted, value, "folder")
        elif type == "item":
            value = make_cipher(value)
            value = encrypt_object(value, self.secrets)
            value = update_request(self.encrypted, value, "cipher")
        else:
            raise NotImplementedError
        value = decrypt_object(value, self.secrets)
        return value

    DELETE_TYPES = {
    }

    def delete(self, uuid, type="item"):
        raise NotImplementedError

    def restore(self, uuid):
        raise NotImplementedError

    LIST_TYPES = {
        "item",
        "folder",
    }

    def list(self, type="item"):
        if type.rstrip("s") == "item":
            return list(self.decrypted["ciphers"].values())
        if type.rstrip("s") == "folder":
            return list(self.decrypted["folders"].values())
        else:
            raise NotImplementedError

    def confirm(self, uuid, organization_id):
        raise NotImplementedError

    def move(self, item_id, organization_id, collection_ids):
        raise NotImplementedError

    def pending(self, organization_id):
        raise NotImplementedError

    def trust(self, organization_id, request_id=None):
        raise NotImplementedError

    def deny(self, organization_id, request_id=None):
        raise NotImplementedError

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

import json
import os
from pathlib import Path
import shutil
import tempfile
import fire
from vaultio.util import SYNC_CACHE, password_input
from vaultio.vault.api import create_vault_secrets, decrypt_blob_from_file, decrypt_blob_stream, decrypt_file_blob_to, decrypt_file_blob_stream, decrypt_object, decrypt_object_key, download_attachment, download_sync

def read_cache(cache):
    with open(cache, "r") as fin:
        return json.load(fin)

def write_data(path, obj, encrypted=True):
    path.mkdir(exist_ok=True)
    if encrypted:
        path = path / "data.json.enc"
    else:
        path = path / "data.json"
    with open(path, "w") as fout:
        json.dump(obj, fout)

def write_blob(path, chunks, encrypted=True):
    path.mkdir(exist_ok=True)
    if encrypted:
        path = path / "data.bin.enc"
    else:
        path = path / "data.bin"
    with open(path, "wb") as fout:
        for chunk in chunks:
            fout.write(chunk)

def decrypt_data(path, secrets):
    with open(path / "data.json.enc", "rb") as fin:
        obj = json.load(fin)
    return decrypt_object(obj, secrets)

def decrypt_blob(path, secrets):
    return decrypt_blob_from_file(path / "data.bin.enc", secrets)

def create_dir(path):
    path = Path(path)
    path.mkdir(exist_ok=True)
    return path

class CLI:

    def login(self, encrypted=None, email=None, password=None, provider_choice=None, provider_token=None, cache=SYNC_CACHE):

        encrypted = download_sync(email, password, provider_choice, provider_token)
        if cache is not None:
            with open(cache, "w") as fout:
                json.dump(encrypted, fout)

    def download(self, destination: Path, cache: Path=SYNC_CACHE):

        encrypted = read_cache(cache)

        destination = create_dir(destination)

        folders_dir = create_dir(destination / "folders")

        folders = list(encrypted["folders"].values())

        for idx, folder in enumerate(folders):

            write_data(folders_dir / folder["id"], folder)

            print(f"folder {idx + 1} / {len(folders)}")

        items_dir = create_dir(destination / "items")

        items = list(encrypted["ciphers"].values())

        failed_attachments = []

        for item_idx, item in enumerate(items):

            item_dir = items_dir / item["id"]

            write_data(item_dir, item)

            print(f"item {item_idx + 1} / {len(items)}")

            attachments_dir = create_dir(item_dir / "attachments")

            if item["attachments"] is None:
                continue

            attachments = item["attachments"]

            for attachment_idx, attachment in enumerate(attachments):

                attachment_dir = create_dir(attachments_dir / attachment["id"])
                print(f"attachment {attachment_idx + 1} / {len(attachments)} ", end="")
                try:
                    chunks = download_attachment(encrypted, item["id"], attachment["id"], decrypted=False)
                    write_blob(attachment_dir, chunks)
                    print("PASS")
                except Exception as e:
                    failed_attachments.append(attachment["id"])
                    print(f"FAIL {e}")
                    shutil.rmtree(attachment_dir)

        print("Failed attachments: [" + ", ".join(failed_attachments) + "]")

    def decrypt(self, destination, password=None, cache: Path=SYNC_CACHE):

        if password is None:
            password = password_input()

        encrypted = read_cache(cache)

        secrets = create_vault_secrets(encrypted, password)

        destination = Path(destination)

        folders_dir = destination / "folders"

        for folder_dir in folders_dir.glob("*"):

            folder = decrypt_data(folder_dir, secrets)

            write_data(folder_dir, folder, False)

        items_dir = destination / "items"

        failed_attachments = []

        for item_dir in items_dir.glob("*"):

            item = decrypt_data(item_dir, secrets)

            write_data(item_dir, item, False)

            if item["attachments"] is None:
                continue

            attachments_dir = item_dir / "attachments"

            for attachment in item["attachments"]:

                attachment_dir = item_dir / attachment["id"]

                attachment_dir = attachments_dir / attachment["id"]

                if not (attachment_dir).exists():
                    continue

                try:
                    attachment_secrets = decrypt_object_key(attachment["key"], secrets)
                    chunks = decrypt_blob(attachment_dir, attachment_secrets)
                    write_blob(attachment_dir, chunks, False)
                    print("PASS")
                except Exception as e:
                    failed_attachments.append(attachment["id"])
                    print(f"{e}")
                    os.unlink(attachment_dir / "data.bin.enc")

def main():
    fire.Fire(CLI())

if __name__ == '__main__':
    main()

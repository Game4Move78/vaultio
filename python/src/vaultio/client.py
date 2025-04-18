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

from vaultio.server import Serve

def remove_none(value):
    ret = {k: v for k, v in value.items() if v is not None}
    return ret or None

def password_input():
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    return simpledialog.askstring("Password", "Enter your password:", show='*')

class Client:

    def __init__(self, socks=None, host=None, port=None, sock_path=None, fd=None, serve=True, wait=True, allow_write=True) -> None:
        self._serve = Serve(socks=socks, host=host, port=port, sock_path=sock_path, fd=fd, serve=serve, wait=wait)
        self.allow_write = allow_write

    def __enter__(self):
        self._serve.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._serve.end()

    def serve(self):
        self._serve.serve_socket()
        self._serve.wait_socket()

    def close(self):
        self._serve.end()

    def lock(self):
        value = self._serve.request_json("/lock", "POST")
        return value["success"]

    def unlock(self, password=None):
        if password is None:
            # import getpass
            # password = getpass.getpass("Enter master password: ")
            password = password_input()
        value = self._serve.request_json("/unlock", "POST", value={"password": password})
        return value["data"]["raw"] if value["success"] else None

    def sync(self):
        value = self._serve.request_json("/sync", "POST")
        return value["success"]

    def status(self):
        value = self._serve.request_json("/status", "GET")
        return value["data"]["template"] if value["success"] else None

    def generate(self, length=None, uppercase=None, lowercase=None, numbers=None, special=None, passphrase=None, words=None, seperator=None, capitalize=None, include_number=None):

        params = remove_none(dict(length=length, uppercase=uppercase, lowercase=lowercase, numbers=numbers, special=special, passphrase=passphrase, words=words, seperator=seperator, capitalize=capitalize, include_number=include_number))

        value = self._serve.request_json("/generate", "GET", params=params)

        return value["data"]["data"]

    def fingerprint(self):
        value = self._serve.request_json("/object/fingerprint/me", "GET")
        return value["data"] if value["success"] else None

    def template(self, type):
        value = self._serve.request_json(f"/object/template/{type}", "GET")
        return value["data"]["template"] if value["success"] else None

    def get_attachment(self, attachment_id, item_id):
        params = dict(itemid=item_id)
        value = self._serve.request_bytes(f"/object/attachment/{attachment_id}", "GET", params=params)
        return value

    def new_attachment(self, uuid, fpath=None):
        assert self.allow_write
        params = dict(itemid=uuid)
        value = self._serve.request_file(f"/attachment", "POST", fpath=fpath, params=params)
        return value["data"] if value["success"] else None

    GET_TYPES = {
        "uri",
        "totp",
        "notes",
        "exposed",
        "password",
        "username",
        "item",
        "folder",
        # ...
    }

    def get(self, uuid, type="item"):
        assert type in self.GET_TYPES
        value = self._serve.request_json(f"/object/{type}/{uuid}", "GET")
        return value["data"] if value["success"] else None

    NEW_TYPES = {
        "item",
        "folder",
        # ...
    }

    def new(self, item, type="item"):
        assert self.allow_write
        if type == "send":
            assert item.get("type") == 0
        value = self._serve.request_json(f"/object/{type}", "GET", value=item)
        return value["data"] if value["success"] else None

    def edit(self, value, type="item"):
        assert self.allow_write
        if type == "send":
            assert value.get("type") == 0
        uuid = value["uuid"]
        value = self._serve.request_json(f"/object/{type}/{uuid}", "PUT", value=value)
        return value["data"] if value["success"] else None

    def delete(self, uuid, type="item"):
        assert self.allow_write
        value = self._serve.request_json(f"/object/{type}/{uuid}", "DELETE")
        return value["success"]

    def restore(self, uuid):
        assert self.allow_write
        value = self._serve.request_json(f"/restore/item/{uuid}", "POST")
        return value["success"]

    def list(self, organization_id=None, collection_id=None, folder_id=None, url=None, trash=None, search=None, type="item"):
        if type.rstrip("s") == "item":
            params = remove_none(dict(organizationId=organization_id, collectionId=collection_id, folderId=folder_id, url=url, trash=trash, search=search))
        else:
            params = remove_none(dict(search=search))
        if type.rstrip("s") == "send":
            type = "send"
        else:
            type = type.rstrip("s") + "s"
        value = self._serve.request_json(f"/list/object/{type}", "GET", params=params)
        return value["data"]["data"] if value["success"] else None

    def confirm(self, uuid, organization_id):
        assert self.allow_write
        params = dict(organizationId=organization_id)
        value = self._serve.request_json(f"/confirm/org-member/{uuid}", "POST", params=params)
        return value

    def move(self, item_id, organization_id, collection_ids):
        assert self.allow_write
        value = self._serve.request_json(f"/move/{item_id}/{organization_id}", "POST", value=collection_ids)
        return value

    def pending(self, organization_id):
        assert self.allow_write
        value = self._serve.request_json(f"/device-approval/{organization_id}", "GET")
        #TODO: Check the return structure
        return value

    def trust(self, organization_id, request_id=None):
        assert self.allow_write
        if request_id is None:
            value = self._serve.request_json(f"/device-approval/{organization_id}/approve-all", "POST")
        else:
            value = self._serve.request_json(f"/device-approval/{organization_id}/approve/{request_id}", "POST")
        return value["success"]

    def deny(self, organization_id, request_id=None):
        assert self.allow_write
        if request_id is None:
            value = self._serve.request_json(f"/deny-approval/{organization_id}/deny-all", "GET")
        else:
            value = self._serve.request_json(f"/device-approval/{organization_id}/deny/{request_id}", "POST")
        return value["success"]

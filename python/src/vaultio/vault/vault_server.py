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

from ..util import password_input, remove_none
from .server import Server

class VaultServer:

    def __init__(self, socks=None, host=None, port=None, sock_path=None, fd=None, serve=True, wait=True, bw_path=None, allow_write=True) -> None:
        self._server = Server(socks=socks, host=host, port=port, sock_path=sock_path, fd=fd, serve=serve, wait=wait, bw_path=bw_path)
        self.allow_write = allow_write

    def __enter__(self):
        self._server.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._server.end()

    def serve(self):
        self._server.serve_socket()
        self._server.wait_socket()

    def close(self):
        self._server.end()

    def lock(self):
        value = self._server.request_json("/lock", "POST")
        return value["success"]

    def unlock(self, password=None):
        if password is None:
            password = password_input()
        value = self._server.request_json("/unlock", "POST", value={"password": password})
        return value["data"]["raw"] if value["success"] else None

    def sync(self):
        value = self._server.request_json("/sync", "POST")
        return value["success"]

    def status(self):
        value = self._server.request_json("/status", "GET")
        return value["data"]["template"] if value["success"] else None

    def generate(self, length=None, uppercase=None, lowercase=None, numbers=None, special=None, passphrase=None, words=None, seperator=None, capitalize=None, include_number=None):

        params = remove_none(dict(length=length, uppercase=uppercase, lowercase=lowercase, number=numbers, special=special, passphrase=passphrase, words=words, seperator=seperator, capitalize=capitalize, includeNumber=include_number))

        value = self._server.request_json("/generate", "GET", params=params)

        return value["data"]["data"] if value["success"] else None

    def fingerprint(self):
        value = self._server.request_json("/object/fingerprint/me", "GET")
        return value["data"] if value["success"] else None

    def template(self, type):
        value = self._server.request_json(f"/object/template/{type}", "GET")
        return value["data"]["template"] if value["success"] else None

    def get_attachment(self, attachment_id, item_id):
        params = dict(itemid=item_id)
        value = self._server.request_bytes(f"/object/attachment/{attachment_id}", "GET", params=params)
        return value

    def new_attachment(self, uuid, fpath=None):
        assert self.allow_write
        params = dict(itemid=uuid)
        value = self._server.request_file(f"/attachment", "POST", fpath=fpath, params=params)
        return value["data"] if value["success"] else None

    GET_TYPES = {
        "totp",
        "notes",
        "exposed",
        "password",
        "username",
        "item",
        "folder",
    }

    def get(self, uuid, type="item"):
        assert type in self.GET_TYPES
        value = self._server.request_json(f"/object/{type}/{uuid}", "GET")
        return value["data"] if value["success"] else None

    NEW_TYPES = {
        "item",
        "send",
        "folder",
        "org-collection",
    }

    def new(self, value, type="item"):
        assert type in self.NEW_TYPES
        assert self.allow_write
        value = self._server.request_json(f"/object/{type}", "GET", value=value)
        return value["data"] if value["success"] else None

    EDIT_TYPES = {
        "item",
        "send",
        "folder",
        "org-collection",
    }

    def edit(self, value, type="item"):
        assert type in self.EDIT_TYPES
        assert self.allow_write
        uuid = value["uuid"]
        value = self._server.request_json(f"/object/{type}/{uuid}", "PUT", value=value)
        return value["data"] if value["success"] else None

    DELETE_TYPES = {
        "item",
        "send",
        "folder",
        "org-collection",
    }

    def delete(self, uuid, type="item"):
        assert self.allow_write
        value = self._server.request_json(f"/object/{type}/{uuid}", "DELETE")
        return value["success"]

    RESTORE_TYPES = {
        "item"
    }

    def restore(self, uuid):
        assert self.allow_write
        value = self._server.request_json(f"/restore/item/{uuid}", "POST")
        return value["success"]

    LIST_TYPES = {
        "item",
        "folder",
        "collections",
        "org-members",
        "organizations",
        "org-collections",
    }

    def list(self, organization_id=None, collection_id=None, folder_id=None, url=None, trash=None, search=None, type="item"):
        assert type in self.LIST_TYPES
        if type.rstrip("s") == "item":
            params = remove_none(dict(organizationId=organization_id, collectionId=collection_id, folderId=folder_id, url=url, trash=trash, search=search))
        else:
            params = remove_none(dict(search=search))
        if type.rstrip("s") == "send":
            type = "send"
        else:
            type = type.rstrip("s") + "s"
        value = self._server.request_json(f"/list/object/{type}", "GET", params=params)
        return value["data"]["data"] if value["success"] else None

    def confirm(self, uuid, organization_id):
        assert self.allow_write
        params = dict(organizationId=organization_id)
        value = self._server.request_json(f"/confirm/org-member/{uuid}", "POST", params=params)
        return value["success"]

    def move(self, item_id, organization_id, collection_ids):
        assert self.allow_write
        value = self._server.request_json(f"/move/{item_id}/{organization_id}", "POST", value=collection_ids)
        return value

    def pending(self, organization_id):
        assert self.allow_write
        value = self._server.request_json(f"/device-approval/{organization_id}", "GET")
        #TODO: Check the return structure
        return value

    def trust(self, organization_id, request_id=None):
        assert self.allow_write
        if request_id is None:
            value = self._server.request_json(f"/device-approval/{organization_id}/approve-all", "POST")
        else:
            value = self._server.request_json(f"/device-approval/{organization_id}/approve/{request_id}", "POST")
        return value["success"]

    def deny(self, organization_id, request_id=None):
        assert self.allow_write
        if request_id is None:
            value = self._server.request_json(f"/deny-approval/{organization_id}/deny-all", "GET")
        else:
            value = self._server.request_json(f"/device-approval/{organization_id}/deny/{request_id}", "POST")
        return value["success"]

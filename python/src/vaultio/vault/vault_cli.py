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
import subprocess
from vaultio.util import BW_PATH, password_input, remove_none

def cli_params(params):
    if params is None:
        return
    for k, v in params.items():
        yield f"--{k}"
        yield str(v)

def json_value(value):
    if value is None:
        return None
    return json.dumps(value)

class VaultCLI:

    def __init__(self, bw_path=None, allow_write=True) -> None:

        if bw_path is None:
            self.bw_path = str(BW_PATH)
        else:
            self.bw_path = bw_path

        self.bw_session = None

        self.allow_write = allow_write

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # self.bw_path = None
        pass

    def run(self, *args, params=None, input=None, stdin=None, stdout=None, **kwds):

        cmd = [str(self.bw_path), *args]

        if params is not None:
            cmd.extend(cli_params(params))

        cmd.extend(["--raw", "--nointeraction"])

        if input is None and stdin is None:
            stdin = subprocess.DEVNULL

        if stdout is None:
            stdout = subprocess.DEVNULL

        env = os.environ.copy()
        if self.bw_session is not None:
            env["BW_SESSION"] = self.bw_session
        env |= {k.upper(): v for k, v in kwds.items()}

        res = subprocess.run(cmd, env=env, stdout=stdout, stderr=subprocess.DEVNULL, input=input, stdin=stdin)

        return res

    def run_quiet(self, *args, params=None, input=None, **kwds):
        return self.run("--quiet", *args, params=params, input=input, **kwds).returncode == 0

    def run_bytes(self, *args, params=None, input=None, **kwds):
        res = self.run(*args, params=params, input=input, stdout=subprocess.PIPE, **kwds)
        if res.returncode == 0:
            return res.stdout
        else:
            return None

    def run_text(self, *args, params=None, input=None, **kwds):
        value = self.run_bytes(*args, params=params, input=input, **kwds)
        if value is None:
            return None
        else:
            return value.decode("utf-8")

    def run_json(self, *args, params=None, input=None, stdin=None, **kwds):
        value = self.run_text(*args, params=params, input=input, stdin=stdin, **kwds)
        if value is None:
            return value
        else:
            return json.loads(value)

    def lock(self):
        return self.run_quiet("unlock")

    def unlock(self, password=None):
        if password is None:
            password = password_input()
        self.bw_session = self.run_text("unlock", "--passwordenv", "PASSWORD", password=password)
        return self.bw_session is not None

    def sync(self):
        return self.run_quiet("sync")

    def status(self):
        return self.run_json("status")

    def generate(
            self, length=None, uppercase=None, lowercase=None, numbers=None, special=None,
            passphrase=None, words=None, seperator=None, capitalize=None, include_number=None,
            ambiguous=None, min_number=None, min_special=None
    ):

        params = remove_none(dict(length=length, uppercase=uppercase, lowercase=lowercase, number=numbers, special=special, passphrase=passphrase, words=words, seperator=seperator, capitalize=capitalize, includeNumber=include_number, ambiguous=ambiguous, minNumber=min_number, minSpecial=min_special))

        return self.run_text("generate", params=params)

    def fingerprint(self):
        return self.run_text("get", "fingerprint", "me")

    def template(self, type):
        return self.run_json("get", "template", type)

    def get_attachment(self, attachment_id, item_id):
        params = dict(itemid=item_id)
        return self.run_bytes("get", "attachment", attachment_id, params=params)

    def new_attachment(self, uuid, fpath=None):
        assert self.allow_write
        params = dict(itemid=uuid)

        if fpath is None:
            return self.run_json("create", "attachment", params=params)
        else:
            with open(fpath, "rb") as fin:
                return self.run_json("create", "attachment", params=params, stdin=fin)

    GET_TYPES = {
        "uri",
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
        return self.run_json("get", type)

    NEW_TYPES = {
        "item",
        "send",
        "folder",
        "org-collection",
    }

    def encode(self, item):
        return self.run("encode", input=json.dumps(item))

    def new(self, value, type="item"):
        assert type in self.NEW_TYPES
        assert self.allow_write
        value = self.encode(value)
        if type == "send":
            return self.run_json("send", "create", input=value)
        else:
            return self.run_json("create", type, input=value)

    EDIT_TYPES = {
        "item",
        "send",
        "folder",
        "org-collection",
    }

    def edit(self, value, type="item"):
        assert type in self.EDIT_TYPES
        assert self.allow_write
        item = self.encode(value)
        if type == "send":
            return self.run_json("send", "edit", input=item)
        else:
            return self.run_json("send", "edit", input=item)

    DELETE_TYPES = {
        "item",
        "send",
        "folder",
        "org-collection",
    }

    def delete(self, uuid, type="item"):
        assert type in self.EDIT_TYPES
        assert self.allow_write
        if type == "send":
            return self.run_json("send", "delete", uuid)
        else:
            return self.run_json("send", "delete", uuid)

    def restore(self, uuid):
        assert self.allow_write
        self.run_json("restore", uuid)

    LIST_TYPES = {
        "item",
        "folder",
        "collections",
        "org-members",
        "organizations",
        "org-collections",
    }

    def list(self, organization_id=None, collection_id=None, folder_id=None, url=None, trash=None, search=None, type="item"):
        if type.rstrip("s") == "item":
            params = remove_none(dict(organizationId=organization_id, collectionId=collection_id, folderId=folder_id, url=url, trash=trash, search=search))
        else:
            params = remove_none(dict(search=search))
        if type.rstrip("s") == "send":
            type = "send"
        else:
            type = type.rstrip("s") + "s"
        return self.run_json("list", type, params=params)

    def confirm(self, uuid, organization_id):
        assert self.allow_write
        params = dict(organizationId=organization_id)
        return self.run_quiet("confirm", uuid, params=params)

    def move(self, item_id, organization_id, collection_ids):
        assert self.allow_write
        collection_ids = self.encode(collection_ids)
        return self.run_json("move", item_id, organization_id, collection_ids)

    def pending(self, organization_id):
        assert self.allow_write
        params=dict(organizationid=organization_id)
        return self.run_json("device-approval", "list", params=params, quiet=True)

    def trust(self, organization_id, request_id=None):
        assert self.allow_write
        params=dict(organizationid=organization_id, request_id=request_id)
        if request_id is None:
            return self.run_quiet("device-approval", "approve-all", params=params, quiet=True)
        else:
            return self.run_quiet("device-approval", "approve", params=params, quiet=True)

    def deny(self, organization_id, request_id=None):
        assert self.allow_write
        params=dict(organizationid=organization_id, request_id=request_id)
        if request_id is None:
            return self.run_quiet("device-approval", "deny-all", params=params, quiet=True)
        else:
            return self.run_quiet("device-approval", "deny", params=params, quiet=True)

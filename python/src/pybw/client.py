import atexit
import itertools
import json
import mimetypes
import os
import re
import socket
import subprocess
from pathlib import Path
import time

from urllib.parse import urlencode
from urllib.parse import urlencode

class HttpResponseError(Exception):

    def __init__(self, status, reason, headers, content) -> None:
        self.status = status
        self.reason = reason
        self.headers = headers
        self.content = content
        super().__init__(f"Http Error [{status}]: {reason}")

class HttpResponse:

    def __init__(self, status, reason, headers, chunks):
        self.status = status
        self.reason = reason
        self.headers = headers
        self.chunks = chunks

    def content(self, check=False):
        if check: self.check()
        return "".join(
            chunk.decode() for chunk in self.chunks
        )

    def check(self):
        if self.status == 200:
            return
        else:
            raise HttpResponseError(self.status, self.reason, self.headers, self.content())

    def json(self, check=False):
        return json.loads(self.content(check))

def serve_socket(socket_path):
    subprocess.Popen(
        ["bw", "serve", "--hostname", f"unix://{socket_path}"],
        start_new_session=True
    )

class Serve:

    def __init__(self, socket_path=None):
        if socket_path is None:
            socket_path = str(Path().absolute() / "pybw.socket")
            self.socket_path=socket_path

        import os

        if not os.path.exists(self.socket_path):
            serve_socket(self.socket_path)

        self.wait_socket()

    def wait_socket(self):
        start = time.time()
        timeout = 5
        interval = .2
        while not os.path.exists(self.socket_path):
            print("Socket doesn't exist")
            time.sleep(interval)
        while True:
            print("Connecting to socket")
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(self.socket_path)
                sock.close()
                return
            except (ConnectionRefusedError, FileNotFoundError) as e:
                print(e)
                # Socket exists but isn't ready yet
                if time.time() - start > timeout:
                    raise TimeoutError(f"Could not connect to socket {self.socket_path} within {timeout} seconds")
            time.sleep(interval)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):

        # Remove the socket file if it exists
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except OSError as e:
                print(f"Error removing socket: {e}")

    def parse_header(self, re_header, bfr):
        m = re_header.match(bfr)

        if m:
            status = int(m.group("status").decode())
            reason = m.group("reason").decode()
            headers = dict(line.split(": ") for line in m.group("headers").decode().splitlines())
            chunk = bfr[m.end():]
            return status, reason, headers, chunk
        else:
            return None

    def request_header(self, sock):

        re_header = re.compile("\r\n".join((
            r"HTTP/1.1 (?P<status>\d{3}) (?P<reason>[^\r\n]+)",
            r"(?P<headers>(?:[^\r\n]+:\s*[^\r\n]*\r\n)*)",
            ""
        )).encode())

        bfr = bytearray()

        while True:
            chunk = sock.recv(4096)
            if not chunk:
                raise Exception(f"Couldn't parse header:\n{bfr.decode()}")
            bfr += chunk
            header = self.parse_header(re_header, bfr)
            if header:
                return header

    def iter_chunks(self, sock, chunk, headers):

        if "Content-Length" in headers:
            content_length = int(headers["Content-Length"])
        else:
            content_length = None

        yield chunk

        if content_length is not None:
            content_length -= len(chunk)

        while content_length is None or content_length >= 0:
            chunk = sock.recv(4096)
            if not chunk:
                break
            yield chunk
            if content_length is not None:
                content_length -= len(chunk)

    # def request_response(self, sock, header):

    #     status, reason, headers, chunk = header

    #     chunks = self.iter_chunks(sock, chunk, content_length)

    #     return HttpResponse(sock, status, reason, headers, chunks)

    def _request(self, endpoint, method, headers=None, body=None, content_type=None, params=None, content_length=None):

        if params is not None:
            endpoint=f"{endpoint}?{urlencode(params)}"

        if headers is None:
            headers = ""
        else:
            headers = "\r\n" + "\r\n".join(f"{k}: {v}" for k, v in headers.items())

        if content_length is not None:
            content_length = str(content_length)
        else:
            content_length = "0"

        data = [
            f"{method} {endpoint} HTTP/1.1",
            "Host: localhost",
            "Connection: close",
            f"Content-Length: {content_length}",
        ]

        if content_type:
            data.append(f"Content-Type: {content_type}")

        data = (("\r\n".join(data) + "\r\n\r\n").encode(),)

        if body is not None:
            data = itertools.chain(data, body)

        print(data)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(self.socket_path)
            bfr = bytearray()
            for chunk in data:
                bfr += chunk
                while len(bfr) >= 4096:
                    sock.sendall(bfr[:4096])
                    bfr = bfr[4096:]
            if len(bfr):
                print(bfr)
                sock.sendall(bfr)
            header = self.request_header(sock)
            status, reason, headers, chunk = header
            print(chunk)
            yield status, reason, headers
            for chunk in self.iter_chunks(sock, chunk, headers):
                print(chunk)
                yield chunk

    def request(self, endpoint, method, headers=None, body=None, content_type=None, params=None, content_length=None):
        chunks = self._request(endpoint, method, headers, body, content_type, params, content_length)
        status, reason, headers = next(chunks)
        return HttpResponse(status, reason, headers, chunks)

    def request_json(self, endpoint, method, headers=None, value=None, params=None, text=False):
        if value is None:
            body = None
            content_length = 0
        else:
            value = json.dumps(value).encode()
            body = (value,)
            content_length = len(value)
        content_type="application/json"
        resp = self.request(endpoint, method, headers, body, content_type, params, content_length)
        if text:
            return resp.content(check=True)
        else:
            return resp.json(check=True)

    def file_pre_body(self, fpath, boundary):
        filename = os.path.basename(fpath)
        mime_type, _ = mimetypes.guess_type(fpath) or "application/octet-stream"
        mime_type = mime_type or "application/octet-stream"
        field_name = "file"

        return ("\r\n".join((
            f"--{boundary}",
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"',
            f"Content-Type: {mime_type}",
        )) + "\r\n\r\n").encode()

    def file_post_body(self, boundary):
        return f"\r\n--{boundary}--\r\n".encode()

    def file_chunks(self, fpath, pre_body, post_body, file_size):

        yield pre_body

        with open(fpath, "rb") as fp:

            while file_size:

                ed = min(file_size, 4096)
                file_size -= ed
                yield fp.read(ed)

        yield post_body

    def request_file(self, endpoint, method, headers=None, fpath=None, params=None):

        boundary="----PyFormBoundary"
        content_type=f"multipart/form-data; boundary={boundary}"

        if fpath is None:
            body = None
            content_length = 0
        else:
            pre_body = self.file_pre_body(fpath, boundary)
            post_body = self.file_post_body(boundary)
            file_size = os.path.getsize(fpath)
            body = self.file_chunks(fpath, pre_body, post_body, file_size)
            content_length = len(pre_body) + file_size + len(post_body)

        resp = self.request(endpoint, method, headers, body, content_type, params, content_length)
        return resp.json(check=True)

def remove_none(value):
    return {k: v for k, v in value.items() if v is not None}

class Client:

    def __init__(self, socket_path=None) -> None:
        self.serve = Serve(socket_path)

    def lock(self):
        value = self.serve.request_json("/lock", "POST")
        return value["success"]

    def unlock(self, password):
        value = self.serve.request_json("/unlock", "POST", value={"password": password})
        return value["data"]["raw"] if value["success"] else None

    def sync(self):
        value = self.serve.request_json("/sync", "POST")
        return value["success"]

    def generate(self, length=None, uppercase=None, lowercase=None, numbers=None, special=None, passphrase=None, words=None, seperator=None, capitalize=None, include_number=None):

        params = remove_none(dict(length=length, uppercase=uppercase, lowercase=lowercase, numbers=numbers, special=special, passphrase=passphrase, words=words, seperator=seperator, capitalize=capitalize, include_number=include_number))

        value = self.serve.request_json("/generate", "GET", params=params)

        return value["data"]["data"]

    def fingerprint(self):
        value = self.serve.request_json("/object/fingerprint/me", "GET")
        return value["data"] if value["success"] else None

    def template(self, type):
        value = self.serve.request_json(f"/object/template/{type}", "GET")
        return value["data"]["template"] if value["success"] else None

    def add_attachment(self, uuid, fpath=None):
        params = dict(itemid=uuid)
        value = self.serve.request_file(f"/attachment", "POST", fpath=fpath, params=params)
        return value["data"] if value["success"] else None

    def get_uri(self, uuid):
        value = self.serve.request_json(f"/object/uri/{uuid}", "GET")
        return value["data"] if value["success"] else None

    def get_totp(self, uuid):
        value = self.serve.request_json(f"/object/totp/{uuid}", "GET")
        return value["data"] if value["success"] else None

    def get_notes(self, uuid):
        value = self.serve.request_json(f"/object/notes/{uuid}", "GET")
        return value["data"] if value["success"] else None

    def get_exposed(self, uuid):
        value = self.serve.request_json(f"/object/exposed/{uuid}", "GET")
        return value["data"] if value["success"] else None

    def get_password(self, uuid):
        value = self.serve.request_json(f"/object/password/{uuid}", "GET")
        return value["data"] if value["success"] else None

    def get_username(self, uuid):
        value = self.serve.request_json(f"/object/username/{uuid}", "GET")
        return value["data"] if value["success"] else None

    def get_attachment(self, attachment_id, item_id):
        params = dict(itemid=item_id)
        value = self.serve.request_json(f"/object/attachment/{attachment_id}", "GET", params=params, text=True)
        return value

    def add_item(self, item):
        value = self.serve.request_json(f"/object/item", "GET", value=item)
        return value

    def get_item(self, uuid):
        value = self.serve.request_json(f"/object/item/{uuid}", "GET")
        return value["data"] if value["success"] else None

    def list_items(self, organization_id=None, collection_id=None, folder_id=None, url=None, trash=None, search=None):
        params = remove_none(dict(organization_id=organization_id, collection_id=collection_id, folder_id=folder_id, url=url, trash=trash, search=search))

        value = self.serve.request_json(f"/list/object/items", "GET", params=params)

        return value["data"] if value["success"] else None

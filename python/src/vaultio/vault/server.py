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

import itertools
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
from email.utils import encode_rfc2231
from urllib.parse import urlencode

from vaultio.util import BW_PATH, CACHE_DIR, SOCK_SUPPORT, kill_process_listening_on_socket

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

    def bytes(self, check=False):
        if check: self.check()
        return b"".join(
            chunk for chunk in self.chunks
        )

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

def require_bw():
    if BW_PATH is None:
        raise Exception("BW CLI not found. Try `vaultio build` to resolve dependencies.")

def require_bw_socks():
    if SOCK_SUPPORT is None:
        raise Exception("BW CLI supporting socket serve not found. Try `vaultio build ` to resolve dependencies.")

def bw_serve(socks=None, host=None, port=None, sock_path=None, fd=None, bw_path=None, **kwds):
    if BW_PATH is None:
        raise Exception("BW CLI supporting socket serve not found. Try `vaultio build` to resolve dependencies.")
    kill_process_listening_on_socket(sock_path)

    if bw_path is None:
        bw_path = BW_PATH

    args = [bw_path, "serve", "--hostname"]

    if socks is not None:
        require_bw_socks()
        fd = socks[1].fileno()
        kwds["pass_fds"] = (fd,)
        args +=  [f"fd+connected://{fd}"]
    elif fd is not None:
        require_bw_socks()
        kwds["pass_fds"] = (fd,)
        args +=  [f"fd+listening://{fd}"]
    elif sock_path is not None:
        require_bw_socks()
        args +=  [f"unix://{sock_path}"]
    else:
        assert host is not None
        args += [str(host)]

    if port is not None:
        args += ["--port", str(port)]

    return subprocess.Popen(
        args,
        **kwds,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

SOCKETPAIR_DEFAULT = True

class Server:

    def __init__(self, socks=None, host=None, port=None, sock_path=None, fd=None, send_sz=4096, recv_sz=4096, serve=True, wait=True, bw_path=None):

        if socks is None and host is None and sock_path is None and fd is None:
            if SOCK_SUPPORT:
                if SOCKETPAIR_DEFAULT:
                    socks = socket.socketpair()
                else:
                    sock_dir = Path.home() / ".cache" / "vaultio" / "socket"
                    sock_path = os.path.join(sock_dir, "serve.sock")
            else:
                host = "localhost"
                port = int(8087)

        self.socks = socks
        self.host = host
        self.port = port
        self.sock_path = sock_path

        self.fd = fd

        self.send_sz = send_sz
        self.recv_sz = recv_sz
        self.serve = serve
        self.wait = wait

        self.bw_path = bw_path

        self.proc = None
        self.start()

        self.bw_path = bw_path

    def serve_socket(self):
        if self.sock_path and os.path.exists(self.sock_path):
            os.unlink(self.sock_path)
        self.proc = bw_serve(self.socks, self.host, self.port, self.sock_path, self.fd, self.bw_path)
        return self.proc

    def start(self):

        if self.proc is not None:
            return

        if self.serve:
            self.proc = self.serve_socket()
        else:
            self.proc = None

        if self.wait:
            self.wait_socket()

    def end(self):

        if self.sock_path and os.path.exists(self.sock_path):
            os.unlink(self.sock_path)

        if self.proc is not None:
            self.proc.terminate()
            self.proc.wait()
            self.proc = None

    def connect_socket(self):
        assert self.socks is None
        if self.sock_path is not None:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.sock_path)
        elif self.fd is not None:
            sock = socket.socket(fileno=self.fd)
        else:
            assert self.host is not None
            if self.port is not None:
                sock = socket.create_connection((self.host, self.port))
            else:
                sock = socket.create_connection((self.host,))
        return sock

    def wait_socket(self):
        start = time.time()
        timeout = 5
        interval = .2
        while self.sock_path is not None and not os.path.exists(self.sock_path):
            # Socket path doesn't exist
            time.sleep(interval)
        while self.socks is None:
            try:
                with self.connect_socket():
                    # Socket exists and connected
                    return
            except (ConnectionRefusedError, FileNotFoundError) as e:
                print(e)
                # Socket exists but isn't ready yet
                time.sleep(interval)
                if time.time() - start > timeout:
                    raise TimeoutError(f"Could not connect to socket {self.sock_path} within {timeout} seconds")
            time.sleep(interval)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):
        # Remove the socket file if it exists
        if self.sock_path:
            if os.path.exists(self.sock_path):
                try:
                    os.remove(self.sock_path)
                except OSError as e:
                    # print(f"Error removing socket: {e}")
                    pass

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
        )).encode("utf-8"))

        bfr = bytearray()

        while True:
            chunk = sock.recv(self.recv_sz)
            if not chunk:
                raise Exception(f"Couldn't parse header:\n{bfr.decode()}")
            bfr += chunk
            header = self.parse_header(re_header, bfr)
            if header:
                return header

    def recv_chunks(self, sock, chunk, headers):

        if "Content-Length" in headers:
            content_length = int(headers["Content-Length"])
        else:
            content_length = None

        yield chunk

        if content_length is not None:
            content_length -= len(chunk)

        while content_length is None or content_length > 0:
            chunk = sock.recv(self.recv_sz)
            if not chunk:
                break
            # print("RECV", chunk)
            yield chunk
            if content_length is not None:
                content_length -= len(chunk)

    def send_chunks(self, sock, chunks):
        bfr = bytearray()
        for chunk in chunks:
            bfr += chunk
            while len(bfr) >= self.recv_sz:
                # print(bfr[:self.recv_sz])
                sock.sendall(bfr[:self.recv_sz])
                # print("SEND", bfr)
                bfr = bfr[self.recv_sz:]
        if len(bfr):
            # print(bfr)
            # print("SEND", bfr)
            sock.sendall(bfr)

    def _request_connected(self, sock, req_chunks, headers=None):
        self.send_chunks(sock, req_chunks)
        header = self.request_header(sock)
        status, reason, headers, chunk = header
        # print(chunk)
        yield status, reason, headers
        for chunk in self.recv_chunks(sock, chunk, headers):
            # print(chunk)
            yield chunk

    def _request(self, endpoint, method, headers=None, body=None, content_type=None, params=None, content_length=None):

        if params is not None:
            endpoint=f"{endpoint}?{urlencode(params)}"

        if headers is None:
            headers = ""
        else:
            headers = "\r\n" + "\r\n".join(f"{k}: {v}" for k, v in headers.items())

        req_chunks = [
            f"{method} {endpoint} HTTP/1.1",
            "Host: localhost"
        ]

        if self.socks is None:
            req_chunks.append("Connection: disconnect")
        else:
            req_chunks.append("Connection: keep-alive")

        if method in ("POST", "PUT"):

            if content_length is not None:
                content_length = str(content_length)
            else:
                content_length = "0"

            req_chunks.append(f"Content-Length: {content_length}")

            if content_type:
                req_chunks.append(f"Content-Type: {content_type}")

        req_chunks = (("\r\n".join(req_chunks) + "\r\n\r\n").encode("utf-8"),)

        if body is not None:
            req_chunks = itertools.chain(req_chunks, body)

        if self.socks is None:
            with self.connect_socket() as sock:
                for chunk in self._request_connected(sock, req_chunks, headers):
                    yield chunk
        else:
            sock = self.socks[0]
            for chunk in self._request_connected(sock, req_chunks, headers):
                yield chunk
            # self.send_chunks(sock, req_chunks)
            # header = self.request_header(sock)
            # status, reason, headers, chunk = header
            # # print(chunk)
            # yield status, reason, headers
            # for chunk in self.recv_chunks(sock, chunk, headers):
            #     # print(chunk)
            #     yield chunk

    def request(self, endpoint, method, headers=None, body=None, content_type=None, params=None, content_length=None):
        chunks = self._request(endpoint, method, headers, body, content_type, params, content_length)
        status, reason, headers = next(chunks)
        return HttpResponse(status, reason, headers, chunks)

    def request_bytes(self, endpoint, method, headers=None, value=None, params=None):
        if value is None:
            body = None
            content_length = None
        else:
            value = json.dumps(value).encode()
            body = (value,)
            content_length = len(value)
        content_type="application/json"
        resp = self.request(endpoint, method, headers, body, content_type, params, content_length)
        return resp.bytes(check=True)

    def request_text(self, endpoint, method, headers=None, value=None, params=None):
        chunks = self.request_bytes(endpoint, method, headers, value, params)
        return chunks.decode()

    def request_json(self, endpoint, method, headers=None, value=None, params=None, text=False):
        text = self.request_text(endpoint, method, headers, value, params)
        return json.loads(text)

    def file_pre_body(self, fpath, boundary):
        filename = encode_rfc2231(os.path.basename(fpath))
        mime_type, _ = mimetypes.guess_type(fpath) or "application/octet-stream"
        mime_type = mime_type or "application/octet-stream"
        field_name = "file"

        return ("\r\n".join((
            f"--{boundary}",
            f'Content-Disposition: form-data; name="{field_name}"; filename*={filename}',
            f"Content-Type: {mime_type}",
        )) + "\r\n\r\n").encode()

    def file_post_body(self, boundary):
        return f"\r\n--{boundary}--\r\n".encode()

    def file_chunks(self, fpath, pre_body, post_body, file_size):

        yield pre_body

        with open(fpath, "rb") as fp:

            while file_size:

                ed = min(file_size, self.send_sz)
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

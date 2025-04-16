import os
from pathlib import Path
import fire
from pybw.build import build
from pybw.client import Client
from pybw.server import HttpResponse, HttpResponseError
from pybw.util import SOCK_SUPPORT

class CLI(Client):

    def __init__(self) -> None:
        if SOCK_SUPPORT:
            sock_dir = Path.home() / ".cache" / "pybw" / "socket"
            sock_path = os.path.join(sock_dir, "serve.sock")
            super().__init__(sock_path=sock_path, serve=False, wait=False)
        else:
            host = "localhost"
            port = int(8087)
            super().__init__(host=host, port=port, serve=False, wait=False)

    def build(self, unofficial=True):
        build(unofficial)

def main():
    try:
        fire.Fire(CLI())
    except HttpResponseError as err:
        print(err.reason, err.content)

if __name__ == '__main__':
    main()

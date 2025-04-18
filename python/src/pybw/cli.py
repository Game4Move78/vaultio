# This file is part of pybw.
#
# pybw is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pybw is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pybw.  If not, see <https://www.gnu.org/licenses/>.


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

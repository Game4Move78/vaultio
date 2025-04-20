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

import cmd
from socket import socketpair

from vaultio.scripts.build import build
from vaultio.vault.server import HttpResponseError
from vaultio.vault import Vault

def safe_cmd(func):
    def wrapper(self, arg):
        try:
            return func(self, arg)
        except HttpResponseError as e:
            print(f"[{e.reason}] {e.content}")
    return wrapper

class Shell(cmd.Cmd):
    intro = "Welcome to the pybw shell. Type help or ? to list commands.\n"
    prompt = "(pybw) "

    def __init__(self, socks=None, host=None, port=None, sock_path=None, fd=None, serve=True, wait=True, bw_path=None, allow_write=True) -> None:
        self.vault = Vault(socks=socks, host=host, port=port, sock_path=sock_path, fd=fd, serve=serve, wait=wait, bw_path=bw_path)
        self.vault.serve()

    def do_build(self, unofficial=False):
        """Build bw cli: build"""
        build(unofficial)

    @safe_cmd
    def do_lock(self, arg):
        """Lock the vault: lock"""
        success = self.vault.lock()
        print("Locked" if success else "Failed to lock")

    @safe_cmd
    def do_unlock(self, arg):
        """Unlock the vault: unlock"""
        result = self.vault.unlock()
        print("Unlocked" if result else "Failed to unlock")

    @safe_cmd
    def do_list(self, arg):
        """List items: list"""
        items = self.vault.list()
        if items is None:
            return None
        for item in items:
            print(item)

    @safe_cmd
    def do_generate(self, arg):
        """Generate a password: generate"""
        print(self.vault.generate())

    @safe_cmd
    def do_status(self, arg):
        """Show vault status: status"""
        print(self.vault.status())

    @safe_cmd
    def do_exit(self, arg):
        """Exit the shell: exit"""
        return self._exit()

    @safe_cmd
    def do_quit(self, arg):
        """Exit the shell: quit"""
        return self._exit()

    @safe_cmd
    def _exit(self):
        self.vault.close()
        return True

if __name__ == '__main__':
    Shell(socks=socketpair()).cmdloop()

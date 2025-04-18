import cmd
from socket import socketpair
from pybw import Client, build
from pybw.server import HttpResponseError

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

    def __init__(self, **kwargs):
        super().__init__()
        self.client = Client(**kwargs)
        self.client.__enter__()

    def do_build(self, unofficial=False):
        """Build bw cli: build"""
        build(official)

    @safe_cmd
    def do_unlock(self, arg):
        """Unlock the vault: unlock"""
        result = self.client.unlock()
        print("Unlocked" if result else "Failed to unlock")

    @safe_cmd
    def do_lock(self, arg):
        """Lock the vault: lock"""
        success = self.client.lock()
        print("Locked" if success else "Failed to lock")

    @safe_cmd
    def do_list(self, arg):
        """List items: list"""
        items = self.client.list()
        for item in items:
            print(item)

    @safe_cmd
    def do_generate(self, arg):
        """Generate a password: generate"""
        print(self.client.generate())

    @safe_cmd
    def do_status(self, arg):
        """Show vault status: status"""
        print(self.client.status())

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
        self.client.__exit__(None, None, None)
        return True

if __name__ == '__main__':
    Shell(socks=socketpair()).cmdloop()

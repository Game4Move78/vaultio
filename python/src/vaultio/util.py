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

from pathlib import Path
import shutil
from tkinter import simpledialog
import psutil
import tkinter as tk
from tkinter import simpledialog, ttk

def kill_process_listening_on_socket(socket_path):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.net_connections(kind='unix'):
                if conn.laddr == socket_path:
                    print(f"Killing PID {proc.pid} ({proc.name()}) listening on {socket_path}")
                    proc.terminate()
                    proc.wait(timeout=2)
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    print(f"No process found listening on {socket_path}")
    return False

CACHE_DIR = Path.home() / ".cache" / "vaultio"

if (CACHE_DIR / "bin" / "bw").exists():
    SOCK_SUPPORT = True
    BW_PATH = CACHE_DIR / "bin" / "bw"
else:
    SOCK_SUPPORT = False
    BW_PATH = shutil.which("bw")

def remove_none(value):
    ret = {k: v for k, v in value.items() if v is not None}
    return ret or None

class InputError(Exception):

    def __init__(self, field) -> None:
        self.field = field
        super().__init__(f"Cancelled input: {field}")

def ask_input(title=None, prompt=None, field="password", show=False):
    if title is None:
        title = f"{field.capitalize()}"
    if prompt is None:
        prompt = f"Enter your {field.lower()}: "
    root = tk.Tk()
    root.withdraw()
    if show:
        show = None
    else:
        show = '*'
    res = simpledialog.askstring(title, prompt, show=show)
    if res is None:
        raise InputError(field)
    return res

password_input = ask_input

class ChoiceDialog(simpledialog.Dialog):
    def __init__(self, parent, title, choices, default=None, prompt=None):
        self.choices = choices
        self.default = default or choices[0]
        self.prompt = prompt or "Choose an option:"
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text=self.prompt).grid(row=0, column=0, sticky="w", padx=10, pady=5)

        self.var = tk.StringVar()
        self.combo = ttk.Combobox(master, textvariable=self.var, values=self.choices, state="readonly")
        self.combo.grid(row=1, column=0, padx=10, pady=5)

        if self.default in self.choices:
            self.combo.set(self.default)
        else:
            self.combo.current(0)

        return self.combo

    def apply(self):
        self.result = self.combo.get()

def choose_input(field, choices, title=None, prompt=None, show=False):
    if title is None:
        title = field.capitalize()
    if prompt is None:
        prompt = f"Choose {field.lower()}:"

    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()

    dialog = ChoiceDialog(root, title, list(choices), default=choices[0], prompt=prompt)
    root.destroy()

    return dialog.result

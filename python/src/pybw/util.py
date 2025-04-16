from pathlib import Path
import shutil
import psutil

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

CACHE_DIR = Path.home() / ".cache" / "pybw"

if (CACHE_DIR / "bin" / "bw").exists():
    SOCK_SUPPORT = True
    BW_PATH = CACHE_DIR / "bin" / "bw"
else:
    SOCK_SUPPORT = False
    BW_PATH = shutil.which("bw")

def remove_none(value):
    ret = {k: v for k, v in value.items() if v is not None}
    return ret or None

def password_input():
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    return simpledialog.askstring("Password", "Enter your password:", show='*')

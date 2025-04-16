import platform
import shutil
import subprocess
from pathlib import Path
from importlib.resources import files
from rich.console import Console
from rich.markup import escape

from pybw.util import CACHE_DIR

console = Console()

def log_step(msg):
    console.log(f":hammer_and_wrench: [bold]{escape(msg)}[/bold]")

def log_info(msg):
    console.log(f":information: [cyan]{escape(msg)}[/cyan]")

def log_done(msg):
    console.log(f":white_check_mark: [green]{escape(msg)}[/green]")

def log_download(msg):
    console.log(f":arrow_down: [bold blue]{escape(msg)}[/bold blue]")

def log_clone(msg):
    console.log(f":inbox_tray: [magenta]{escape(msg)}[/magenta]")

def log_move(msg):
    console.log(f":package: [yellow]{escape(msg)}[/yellow]")

def build_nodeenv():
    log_download("⬇️  Installing Node and npm into the virtualenv...")
    subprocess.run(
        # ["nodeenv", "-p", str(venv), "-n", "20.18.0", "--npm", "none"],
        ["nodeenv", "-p", "-n", "20.18.0", "--npm", "none"],
        check=False,
        text=True
    )

def clone_bw():

    root_dir = CACHE_DIR / "clients"
    cli_dir = root_dir / "apps" / "cli"

    repo_url = "https://github.com/Game4Move78/clients"

    log_clone(f"Cloning Bitwarden CLI from {repo_url}")
    subprocess.run(["git", "clone", repo_url, str(root_dir), "--depth", "1", "--single-branch", "--branch", "feat/unix-socket-support"], check=True)

    assert root_dir.exists()
    assert cli_dir.exists()

    return root_dir, cli_dir

def get_pkg_script():
    system = platform.system()
    machine = platform.machine()

    if system == "Linux":
        return "package:oss:lin", "dist/oss/linux/bw"
    elif system == "Darwin":
        if machine == "arm64":
            return "package:oss:mac-arm64", "dist/oss/macos-arm64/bw"
        else:
            return "package:oss:mac", "dist/oss/macos/bw"
    elif system == "Windows":
        return "package:oss:win", "dist/oss/windows/bw.exe"
    else:
        raise RuntimeError(f"Unsupported platform: {system} ({machine})")

PACKAGE_SCRIPT, BW_PATH = get_pkg_script()

def build_bw():

    root_dir, cli_dir = clone_bw()

    log_done(f"Bitwarden CLI repo found in {root_dir}")

    assert cli_dir.exists(), f"Expected BW directory not found at: {cli_dir}"
    assert cli_dir.exists(), f"Expected BW CLI directory not found at: {cli_dir}"

    log_download("Installing Bitwarden CLI dependencies...")
    subprocess.run(["npm", "install", "-w", "@bitwarden/cli", "--ignore-scripts"], cwd=root_dir, check=True)
    subprocess.run(["npm", "install", "-w", "@bitwarden/cli", "--ignore-scripts"], cwd=cli_dir, check=True)
    subprocess.run(["npm", "install", "-D", "cross-env", "webpack", "tsconfig-paths-webpack-plugin"], cwd=root_dir, check=True)

    log_step("Building Bitwarden CLI...")
    subprocess.run(["npm", "run", "build:oss:prod", "-w", "@bitwarden/cli"], cwd=root_dir, check=True)
    subprocess.run(["npm", "run", PACKAGE_SCRIPT, "-w", "@bitwarden/cli"], cwd=root_dir, check=True)

    if (cli_dir / BW_PATH).exists():
        print(f"{(cli_dir / BW_PATH)} exists. Removing...")
        shutil.rmtree(root_dir)
    log_move(f"Moving {BW_PATH} from {cli_dir} into {CACHE_DIR}")
    shutil.move(cli_dir / BW_PATH, CACHE_DIR / "bin")

    log_info(f"Cleaning up {root_dir}")

    shutil.rmtree(root_dir)

def build(unofficial=True):
    if unofficial:
        log_info("Unofficial build mode: building Bitwarden CLI fork from source.")
        build_nodeenv()
        build_bw()
    else:
        log_info("Official mode: Installing Bitwarden CLI via npm.")
        if not shutil.which("npm"):
            build_nodeenv()
        log_download(f"Installing @bitwarden/cli globally with prefix {CACHE_DIR}")
        subprocess.run(["npm", "install", "@bitwarden/cli", "-g", "--prefix", CACHE_DIR], check=True)
        log_done("Installation complete.")

def has_bw():
    return shutil.which("node") and (CACHE_DIR / "build").exists()

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

import platform
import shutil
import subprocess
from pathlib import Path
from importlib.resources import files
from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt

from vaultio.util import CACHE_DIR

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
    node_path = shutil.which("node")
    if node_path is not None:
        version = subprocess.run([node_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False).stdout
        if version.decode("utf-8").strip() == "v20.18.0":
            return
    log_download("⬇️  Installing Node and npm into the virtualenv...")
    subprocess.run(
        ["nodeenv", "-p", "-n", "20.18.0", "--npm", "none"],
        check=True,
        text=True,
    )

def clone_bw():

    root_dir = CACHE_DIR / "clients"
    cli_dir = root_dir / "apps" / "cli"

    if root_dir.exists():
        log_info(f"Cleaning up {root_dir}")
        shutil.rmtree(root_dir)

    repo_url = "https://github.com/Game4Move78/clients"
    repo_branch = "vaultio"

    upstream_url = "https://github.com/bitwarden/clients"
    upstream_branch = "main"

    log_clone(f"Cloning Bitwarden CLI from {repo_url}")
    subprocess.run(["git", "clone", repo_url, str(root_dir), "--depth", "1", "--single-branch", "--branch", repo_branch], check=True)

    log_info(f"Showing difference from official")
    subprocess.run(["git", "remote", "set-url", "upstream", upstream_url], check=True)
    subprocess.run(["git", "fetch", "upstream"], check=True)
    subprocess.run(["git", "--no-pager", "diff", "upstream/main..vaultio"], check=True)

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

    resp = Prompt.ask(
        "[bold yellow]:construction: Diff against official repo[/bold yellow]. Proceed with build?",
        choices=["y", "n"],
        default="n",
        show_choices=False
    ).strip().lower()

    if resp.strip().lower()[:1] != "y":
        print("Aborting.")
        return

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

    log_move(f"Moving {BW_PATH} from {cli_dir} into {CACHE_DIR}")
    src = cli_dir / BW_PATH
    dst = CACHE_DIR / "bin" / "bw"
    dst.unlink(missing_ok=True)
    shutil.move(src, dst)

    log_info(f"Cleaning up {root_dir}")

    shutil.rmtree(root_dir)

def build(unofficial=False):
    choice = Prompt.ask(
        "\n[bold cyan]:rocket: Build Bitwarden CLI[/bold cyan]\n"
        ":point_right: Choose a source:\n"
        "  [green]official[/green]   - install via npm\n"
        "  [magenta]unofficial[/magenta] - build fork from source\n",
        choices=["official", "unofficial"],
        default="unofficial" if unofficial else "official"
    )
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

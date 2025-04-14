import subprocess
from pathlib import Path
import nodeenv
import argparse

def get_poetry_venv():
    result = subprocess.run(
        ["poetry", "env", "info", "-p"],
        stdout=subprocess.PIPE,
        check=True,
        text=True
    )
    return result.stdout.strip()

def create_nodenv():

    result = subprocess.run(
        ["nodeenv", "-p", str(venv), "-n", "20.18.0", "--npm", "none"],
        stdout=subprocess.PIPE,
        check=True,
        text=True
    )
    if result.returncode != 0:
        print("nodeenv failed:")
        print("stdout:", result.stdout)
        print("stderr:", result.stderr)
        result.check_returncode()  # this will still raise the same error, but now with info

    return result.stdout.strip()

def install_bw():

    venv = get_poetry_venv()

    bw_path = Path(venv) / "bin" / "bw"

    if bw_path.exists():
        print("Node and npm already installed in virtualenv, skipping nodeenv setup.")
        return

    root_dir = Path(__file__).absolute().parents[3] / "clients"
    cli_dir = root_dir / "apps" / "cli"

    assert cli_dir.exists(), f"Expected CLI directory not found at: {cli_dir}"

    print(f"Installing clients")

    subprocess.run(["npm", "install", "-w", "@bitwarden/cli"], cwd=root_dir, check=True)

    print(f"Installing cli")

    subprocess.run(["npm", "install", "-w", "@bitwarden/cli"], cwd=cli_dir, check=True)

    print(f"Building cli")

    subprocess.run(["npm", "run", "build:prod", "-w", "@bitwarden/cli"], cwd=cli_dir, check=True)

    print(f"Linking bw")

    subprocess.run(["npm", "link"], cwd=cli_dir, check=True)

def install():

    venv = get_poetry_venv()
    print(f"Using Poetry virtualenv at {venv}")

    node_path = Path(venv) / "bin" / "node"
    npm_path = Path(venv) / "bin" / "npm"

    if node_path.exists() and npm_path.exists():
        print("Node and npm already installed in virtualenv, skipping nodeenv setup.")
    else:
        create_nodenv()

    bw_path = Path(venv) / "bin" / "bw"

    if bw_path.exists():
        print("bw already installed in virtualenv, skipping bw setup.")
    else:
        install_bw()

install()

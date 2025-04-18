# Python API for Bitwarden Vault Management

## Overview

**`pybw`** is an **unofficial Python API** for managing Bitwarden vaults via the Bitwarden CLI. Instead of launching a new CLI process for each operation, it runs the CLI once in the background and communicates with it through a **private socket connection**. This improves performance and provides a secure method for using the [serve API](https://bitwarden.com/help/vault-management-api/).

## How It Works

The API is built around the stateful Express web server launched by the [`bw serve`](https://bitwarden.com/help/cli/#serve) command. This server exposes a local REST API for performing vault actions. `pybw` wraps this API internally and delegates all actions to the Bitwarden CLI.

> **Note:** `pybw` does **not cache or store credentials**. All requests are proxied directly to the background process.

---

## Installation

### 🔧 Basic Setup

```sh
cd python
python -m venv .venv
source .venv/bin/activate
pip install poetry
poetry install
```

---

## Installing the Bitwarden CLI

### Option 1: Official CLI

By default, `bw serve` exposes its API via **HTTP over TCP**, which can be less secure since other users or apps might access the unlocked vault without proper firewall rules.

You can either:
- Ensure `bw` is available in your `PATH`, or
- Run:

```sh
pybw build
```

This installs the CLI from the official NPM package [`@bitwarden/cli`](https://www.npmjs.com/package/@bitwarden/cli).

### Option 2: Unofficial Fork with Socket Support

A [pull request](https://github.com/bitwarden/clients/pull/14262) introduces support for **Unix sockets** and other socket types in `bw serve`. This allows communication without traversing the network stack, improving security.

To enable this:
- **Manually build** from the fork: [Game4Move78/clients](https://github.com/Game4Move78/clients/tree/feat/unix-socket-support) and copy the binary to:

```sh
$HOME/.cache/pybw/bin/bw
```

- **Or**, let `pybw` handle it for you:

```sh
pybw --unofficial
```

This will clone the repo and build it locally. (No pre-built binaries are currently provided.)

---

## Usage

### 📘 API Documentation

See the full [API reference](https://github.com/Game4Move78/pybw/blob/master/API.md).

### 📟 CLI Wrapper

```sh
pybw --help
```

### 🧪 Example: Check Status and List Items

```python
from pybw.client import Client

with Client() as client:
    print(client.status())
    print(client.unlock())
    print(client.status())

    for item in client.list():
        print(item["name"])

    for folder in client.list(type="folder"):
        print(folder["name"])
```

### 🔍 More Examples

- [Creating a CLI](https://github.com/Game4Move78/pybw/blob/master/python/src/pybw/cli.py)
- [Creating a shell](https://github.com/Game4Move78/pybw/blob/master/python/src/pybw/examples/shell.py)
- [Backing up vault to Unix pass](https://github.com/Game4Move78/pybw/blob/master/python/src/pybw/examples/backup.py)

---

## 🔐 HTTPS Support

Not currently supported directly, but it's possible using [Caddy](https://github.com/Game4Move78/bw-serve-encrypted).

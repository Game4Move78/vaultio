# Unofficial Python API for Bitwarden Vault Management

## Overview

**`vaultio`** is an **unofficial Python API** for managing Bitwarden vaults via the Bitwarden CLI. Instead of launching a new CLI process for each operation, it runs the CLI once in the background and communicates with it through a **private socket connection**. This improves performance and provides a secure method for using the [serve API](https://bitwarden.com/help/vault-management-api/) to build tools and scripts.

## How It Works

The API is built around the stateful Express web server launched by the [`bw serve`](https://bitwarden.com/help/cli/#serve) command. This server exposes a local REST API for performing vault actions. `vaultio` wraps this API internally and delegates all actions to the Bitwarden CLI.

> **Note:** `vaultio` does **not cache or store credentials**. All requests are proxied directly to the background process.

---

## Installation

### 📦 Pip

```sh
pip install vaultio
```

### 🔧 Repo

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
vaultio build
```

This installs the CLI from the official NPM package [`@bitwarden/cli`](https://www.npmjs.com/package/@bitwarden/cli).

### Option 2: Unofficial Fork with Socket Support

I made a [pull request](https://github.com/bitwarden/vaults/pull/14262) that introduces support for Unix sockets and other socket types in `bw serve`. This allows communication without traversing the network stack, improving security.

To enable this:
- **Manually build** from the fork: [Game4Move78/vaults#vaultio](https://github.com/Game4Move78/vaults/tree/feat/vaultio) and copy the binary to:

```sh
$HOME/.cache/vaultio/bin/bw
```

- **Or**, let `vaultio` handle it for you:

```sh
vaultio --unofficial
```

This will clone the repo and build it locally. Then it will show you a diff against the [official repo](https://github.com/bitwarden/vaults) before prompting you to continue.

---

## Usage

### 📘 API Documentation

See the full [API reference](https://github.com/Game4Move78/vaultio/blob/master/API.md).

### 📟 CLI Wrapper

```sh
vaultio --help
```

### 🧪 Example: Check Status and List Items

```python
from vaultio.vault import Vault

with Vault() as vault:
    print(vault.status())
    print(vault.unlock())
    print(vault.status())

    for item in vault.list():
        print(item["name"])

    for folder in vault.list(type="folder"):
        print(folder["name"])
```

### 🔍 More Examples

- [Creating a CLI](https://github.com/Game4Move78/vaultio/blob/master/python/src/vaultio/cli.py)
- [Creating a shell](https://github.com/Game4Move78/vaultio/blob/master/python/src/vaultio/examples/shell.py)
- [Backing up vault to Unix pass](https://github.com/Game4Move78/vaultio/blob/master/python/src/vaultio/examples/backup.py)

---

## 🔐 HTTPS Support

Not currently supported directly, but it's possible using [Caddy](https://github.com/Game4Move78/bw-serve-encrypted).

## Related

- [`PyWarden`](https://github.com/stefanfluit/PyWarden) is a Python Bitwarden CLI wrapper

## Disclaimer

This project is not associated with [https://bitwarden.com/](Bitwarden) or Bitwarden, Inc. These contributions are independent of Bitwarden and are reviewed by other maintainers.

Please note: We cannot be held liable for any data loss that may occur while using `vaultio`. This includes passwords, attachments, and other information handled by the application. We highly recommend performing regular backups of your files and database. However, should you experience data loss, we encourage you to contact us immediately.

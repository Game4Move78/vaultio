# Python API for Bitwarden Vault Management

## Description
This an unofficial Python API for Bitwarden Vault Management using the Bitwarden CLI. Rather than launching the CLI app repeatedly for every action, it launches the CLI once in a background process and sends commands through a private socket connection.

## Implementation
The implementation is built around the stateful express web server launched by the [serve](https://bitwarden.com/help/cli/#serve) command, which deploys a local REST API for performing CLI actions. `pybw` uses this API internally, relying on the Bitwarden CLI for all actions. It never caches any credentials that are served and simply passes requests onto the Bitwarden background process and returns the results.

## Basic install

```sh
cd python
python -m venv .venv
source .venv/bin/activate
pip install poetry
poetry install
```

## Installing official Bitwarden CLI
Currently the serve API is only exposed through HTTP over a TCP port. This makes setting permissions difficult, as you have to manually set up a firewall to stop other apps and users from being able to interact with the unlocked vault. To use the official CLI either have `bw` available on your PATH or you can run `pybw build` to install it from the official NPM package `@bitwarden/cli`.

## Installing unofficial fork adding socket support
I have made a [PR](https://github.com/bitwarden/clients/pull/14262) that makes a small external change to `bw serve` so that it can serve over various types of socket connections. This means that requests can not be seen by other users and processes and will be sent to the process directly over a socket connection rather than passing through the network stack unencrypted. The changes are minor and the diff can be reviewed [here](https://github.com/bitwarden/clients/pull/14262/files).

To enable this functionality currently you have to either build from source using [fork](https://github.com/Game4Move78/clients/tree/feat/unix-socket-support) and copy the binary to `$HOME/.cache/pybw/bin/bw`. Alternatively you can run `pybw --unofficial` and it will build clone the repo and build from source for you. Currently there is no pre-packaged binaries.

## Usage

### CLI wrapper

```shell
pybw --help
```

### Print status and names for items and folders

```python
with Client() as client:
    print(client.status()) # asks for status
    print(client.unlock())
    print(client.status())
    for item in client.list():
        print(item["name"])
    for folder in client.list(type="folder"):
        print(item["name"])
```

### More examples

- [Creating a CLI](https://github.com/Game4Move78/pybw/blob/master/python/src/pybw/cli.py)
- [Creating a shell](https://github.com/Game4Move78/pybw/blob/master/python/src/pybw/examples/shell.py)
- [Backing up vault to Unix pass](https://github.com/Game4Move78/pybw/blob/master/python/src/pybw/examples/backup.py)

## Does it support HTTPS?

Not supported, but its possible using [caddy](https://github.com/Game4Move78/bw-serve-encrypted).

# Python API for Bitwarden Vault Management

## Description

This an unofficial Python API for Bitwarden, utilising the stateful local express web server that comes as part of the command line client. The [bw serve](https://bitwarden.com/help/cli/#serve) command launches an offline REST API for vault management, and this is a Python API to use its endpoints. This interface is stateless and never caches credentials that are served, and simply passes requests onto the Bitwarden background process through a socket connection.

Currently Bitwarden only serves this API through HTTP over a local TCP port, which has security risks if not guarded properly. To address this, I have made a [PR](https://github.com/bitwarden/clients/pull/14262) that may or may not get merged, but allows restricting the CLI server to socket-based and IPC-style communication. This means that requests can not be seen by other users and processes, communicating over socket.socketpair or bound unix domain sockets.

## Why not invoke the BW CLI for every command?

You can! It just requires launching the nodejs app every time. This method is fast because it communicates directly over sockets or over the network.

## Install

```sh
cd python
python -m venv .venv
source .venv/bin/activate
pip install poetry
poetry install
```

## Installing CLI

### Official

Using Bitwarden's npm package.

```sh
pybw build
```

### Fork (for socket support)

This version is built from source using my [fork](https://github.com/Game4Move78/clients/tree/feat/unix-socket-support) of the Bitwarden repo. The changes are minor and can be viewed [here](https://github.com/bitwarden/clients/pull/14262/files).

```sh
pybw build --unofficial
```

## Basic Usage

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

## More examples

See [shell.py](https://github.com/Game4Move78/pybw/blob/master/python/src/pybw/shell.py) and [cli.py](https://github.com/Game4Move78/pybw/blob/master/python/src/pybw/cli.py) for examples.

## Does it support HTTPS?

Not supported, but its possible using [caddy](https://github.com/Game4Move78/bw-serve-encrypted).

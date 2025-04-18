# Client API

This `Client` class provides a Python interface for interacting with Bitwarden CLI serve. It wraps JSON-based API endpoints for various operations, such as user authentication, item management, syncing, and attachment handling.

---

## Initialization

```python
client = Client(host="127.0.0.1", port=8087)
```

**Parameters:**
- `socks`: Pre-existing socket connections (optional)
- `host`: Server host
- `port`: Server port
- `sock_path`: Unix socket path (optional)
- `fd`: File descriptor (optional)
- `serve`: Whether to start the server
- `wait`: Whether to wait for socket readiness
- `allow_write`: If `False`, disables all mutating operations

---

## Context Manager Support

```python
with Client(...) as client:
    ...
```
- Automatically starts and stops the underlying server connection.

---

## Core Methods

### `client.serve()`
Starts serving and waits for socket readiness.

### `client.close()`
Stops the server.

---

## Authentication Methods

### `client.lock()`
Locks the vault.

### `client.unlock(password=None)`
Unlocks the vault. Prompts for password if not provided.

### `client.sync()`
Syncs with the server.

### `client.status()`
Returns vault status.

---

## Password Generation

### `client.generate(...)`
Generates a new password or passphrase.

**Optional parameters:**
- `length`, `uppercase`, `lowercase`, `numbers`, `special`
- `passphrase`, `words`, `separator`, `capitalize`, `include_number`

---

## Template and Object Info

### `client.template(type)`
Gets the creation template for a specific object type.

### `client.fingerprint()`
Returns the server's fingerprint.

---

## Object Management

### `client.get(uuid, type="item")`
Retrieves a specific object.

### `client.new(item, type="item")`
Creates a new object.

### `client.edit(item, type="item")`
Edits an existing object.

### `client.delete(uuid, type="item")`
Deletes an object.

### `client.restore(uuid)`
Restores a previously deleted item.

### `client.list(...)`
Lists objects filtered by:
- `organization_id`, `collection_id`, `folder_id`, `url`, `trash`, `search`, `type`

---

## Attachments

### `client.get_attachment(attachment_id, item_id)`
Downloads an attachment.

### `client.new_attachment(uuid, fpath=None)`
Uploads a new attachment for an item.

---

## Organization Management

### `client.confirm(uuid, organization_id)`
Confirms organization membership.

### `client.move(item_id, organization_id, collection_ids)`
Moves an item to collections in an organization.

### `client.pending(organization_id)`
Lists pending approvals.

### `client.trust(organization_id, request_id=None)`
Approves a device (or all devices).

### `client.deny(organization_id, request_id=None)`
Denies a device (or all devices).

---

## Notes
- `allow_write=False` disables `new`, `edit`, `delete`, `trust`, etc.

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.


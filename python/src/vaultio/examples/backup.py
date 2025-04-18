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

from csv import Error
import os
from pathlib import Path
import subprocess

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from vaultio.client import Client

from faker import Faker

faker = Faker()

def iter_items(client):
    folder_map = {f["id"]: f["name"] for f in client.list(type="folder")}

    for item in client.list():
        path = Path(folder_map[item["folderId"]]) / item["name"]
        yield path, item

def pass_insert(path, value):
    subprocess.check_output(["pass", "insert", "-m", path], input=value)

def getpath(entry, value_path):
    for k in value_path.split("/"):
        if (isinstance(k, str) and k in entry) or (isinstance(k, int) and k < len(entry)):
            entry = entry[k]
        else:
            return None
    return entry

def backup_value(entry_path, entry, value_path):
    value = getpath(entry, value_path)
    if value is not None:
        pass_insert(entry_path / value_path, value.encode("utf-8"))

def backup_attachments(client, display, item_path, item):

    for attachment in item.get("attachments", ()):
        attachment_path = item_path / "attachments" / attachment["fileName"]
        pass_insert(attachment_path, client.get_attachment(attachment["id"], item["id"]))
        display.add_backup_attachment(attachment["fileName"], attachment["id"])

def counts(entries):
    cts = {}
    for entry in entries:
        if entry["name"] in cts:
            cts[entry["name"]] += 1
        else:
            cts[entry["name"]] = 1
    return cts

def backup_fields(item_path, item):
    if item.get("fields") is None:
        return

    cts = counts(item["fields"])

    for field in item["fields"]:

        field_path = item_path / "fields" / field["name"]

        if cts[field["name"]] != 1 or field["name"] == "fields" or field["value"] is None:
            # print(f"Ignored field {field_path}")
            continue

        pass_insert(field_path, field["value"].encode())

def backup(client, display, item_path, item):

    backup_value(item_path, item, "id")
    backup_value(item_path, item, "login/username")
    backup_value(item_path, item, "login/password")
    backup_value(item_path, item, "notes")
    backup_fields(item_path, item)
    backup_attachments(client, display, item_path, item)

class Display:

    def __init__(self, live) -> None:
        self.live = live
        self.items = []        # List of (name, uuid)
        self.attachments = []  # List of (filename, uuid)

    def add_backup_item(self, name, uuid):
        name = faker.url()
        uuid = faker.uuid4()
        self.items.append((name, uuid))
        self.items = self.items[-5:]

    def add_backup_attachment(self, fn, uuid):
        fn = faker.file_name()
        uuid = faker.password(length=32, special_chars=False, upper_case=False)
        self.attachments.append((fn, uuid))
        self.attachments = self.attachments[-5:]

    def _build_table(self, rows, col1, col2):
        table = Table.grid(padding=(0, 1))
        table.add_column(col1, style="bold")
        table.add_column(col2, style="dim")

        if rows:
            for a, b in rows:
                table.add_row(a, b)
        else:
            table.add_row("[dim]None yet[/]", "")

        return table

    def update(self, total, idx):

        progress = Table.grid()
        progress.add_column()
        progress.add_row(f"{(idx + 1) / total * 100:.1f}%")

        items_panel = Panel(
            self._build_table(self.items, "Item", "ID"),
            title="Backed Up Items",
            border_style="green"
        )

        attachments_panel = Panel(
            self._build_table(self.attachments, "File", "ID"),
            title="Backed Up Attachments",
            border_style="green"
        )

        progress_panel = Panel(progress, title="Backup Progress", border_style="green")

        layout = Group(items_panel, attachments_panel, progress_panel)
        self.live.update(layout)

def main():
    with Client() as client, Live(refresh_per_second=30) as live:
        display = Display(live)
        client.unlock()

        items = list(iter_items(client))
        cts = counts(item for _, item in items)
        total = len(items)

        for idx, (item_path, item) in enumerate(items):

            if cts[item["name"]] != 1:
                continue

            backup(client, display, Path("bitwarden") / item_path, item)
            display.add_backup_item(item["name"], item["id"])
            display.update(total, idx)

if __name__ == "__main__":
    main()

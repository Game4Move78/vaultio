import vaultio

def main():

    with vaultio.VaultCLI(dry_run=True) as vault:

        vault.unlock()

        collections = vault.list(type="collection")

        choices = {x["name"]: x for x in collections}

        src = vaultio.util.choose_input("source", list(choices.keys()))
        if src is None:
            return

        dst = vaultio.util.choose_input("destination", list(choices.keys()))
        if dst is None:
            return

        src = choices[src]
        dst = choices[dst]

        for item in vault.list(type="item"):
            ids = set(item["collectionIds"])
            if src["id"] in ids and dst["id"] not in ids:
                item["organizationId"] = dst["organizationId"]
                item["collectionIds"] = [dst["id"]]
                new_item = vault.new(item, type="item")
                vault.delete(item["id"], type="item")

main()

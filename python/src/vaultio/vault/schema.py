ENCRYPTED_KEYS = {
    # Core cipher fields
    "name",
    "notes",

    # Login object
    "username",
    "password",
    "totp",
    "uri",     # legacy single URI field
    "uris",    # newer URI list (each uri.value is encrypted)

    # Fields (custom fields)
    "value",   # name and value are both encrypted

    # Card object
    "cardholderName",
    "brand",
    "number",
    "expMonth",
    "expYear",
    "code",

    # Identity object
    "title",
    "firstName",
    "middleName",
    "lastName",
    "address1",
    "address2",
    "address3",
    "city",
    "state",
    "postalCode",
    "country",
    "company",
    "email",
    "phone",
    "ssn",
    "username",

    # Secure note
    "secureNote",

    # Attachment metadata
    "fileName",
}

INTERNAL_KEYS = {
    "key",
    "uriChecksum",
    "id", "type", "object", "folderId",
    "organizationId", "collectionIds"
}

CIPHER_TYPE_DEFAULTS = {
    1: {  # Login
        "login": {
            "username": None,
            "password": None,
            "totp": None,
            "uris": []
        }
    },
    2: {  # Secure Note
        "secureNote": {},
    },
    3: {  # Card
        "card": {
            "cardholderName": None,
            "brand": None,
            "number": None,
            "expMonth": None,
            "expYear": None,
            "code": None
        }
    },
    4: {  # Identity
        "identity": {
            "title": None,
            "firstName": None,
            "middleName": None,
            "lastName": None,
            "address1": None,
            "address2": None,
            "address3": None,
            "city": None,
            "state": None,
            "postalCode": None,
            "country": None,
            "company": None,
            "email": None,
            "phone": None,
            "ssn": None,
            "username": None,
            "passportNumber": None,
            "licenseNumber": None
        }
    },
    5: {},  # Hidden fields — typically user-defined `fields` used
}

def make_cipher(cipher: dict) -> dict:
    from copy import deepcopy

    c = deepcopy(cipher)
    c.setdefault("type", 1)
    c.setdefault("name", None)
    c.setdefault("notes", None)
    c.setdefault("organizationId", None)
    c.setdefault("folderId", None)
    c.setdefault("favorite", False)
    c.setdefault("reprompt", 0)
    c.setdefault("fields", None)
    c.setdefault("attachments", None)
    c.setdefault("card", None)
    c.setdefault("identity", None)
    c.setdefault("secureNote", None)
    c.setdefault("sshKey", None)
    c.setdefault("key", None)
    c.setdefault("object", "cipherDetails")


    type_defaults = CIPHER_TYPE_DEFAULTS.get(c["type"], {})
    for key, value in type_defaults.items():
        c.setdefault(key, value)

    return c

TEMPLATES = {
    "cipher": {
        "type": 1,
        "name": "...",
        "notes": None,
        "organizationId": None,
        "folderId": None,
        "favorite": False,
        "reprompt": 0,
        "login": {
            "username": "...",
            "password": "...",
            "totp": None,
            "uris": []
        },
        "fields": None,
        "attachments": None,
        "card": None,
        "identity": None,
        "secureNote": None,
        "sshKey": None,
        "key": "...",
        "object": "cipherDetails"
    }
}

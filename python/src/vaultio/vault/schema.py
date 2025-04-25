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

    cipher = deepcopy(cipher)
    cipher.setdefault("type", 1)
    cipher.setdefault("name", None)
    cipher.setdefault("notes", None)
    cipher.setdefault("organizationId", None)
    cipher.setdefault("folderId", None)
    cipher.setdefault("favorite", False)
    cipher.setdefault("reprompt", 0)
    cipher.setdefault("fields", None)
    cipher.setdefault("attachments", None)
    cipher.setdefault("card", None)
    cipher.setdefault("identity", None)
    cipher.setdefault("secureNote", None)
    cipher.setdefault("sshKey", None)
    cipher.setdefault("key", None)
    cipher.setdefault("object", "cipherDetails")


    type_defaults = CIPHER_TYPE_DEFAULTS.get(cipher["type"], {})
    for key, value in type_defaults.items():
        cipher.setdefault(key, value)

    return cipher

def make_attachment(attachment: dict) -> dict:
    from copy import deepcopy

    attachment = deepcopy(attachment)
    attachment.setdefault("id", None)
    assert "fileName" in attachment
    attachment.setdefault("size", 0)
    attachment.setdefault("url", None)
    attachment.setdefault("object", "attachment")

    return attachment

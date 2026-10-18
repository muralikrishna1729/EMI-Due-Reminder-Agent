import hashlib


def hash_code(code: str, salt: str) -> str:
    return hashlib.sha256((salt + code).encode()).hexdigest()


def mask_name(name: str) -> str:
    parts = name.split(" ")
    return " ".join(
        p if i == 0 else p[0] + "*" * max(len(p) - 1, 1) for i, p in enumerate(parts)
    )
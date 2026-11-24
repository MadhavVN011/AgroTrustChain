"""Password hashing for the Users table (Werkzeug's salted hashes; Werkzeug ships with Flask).

Older databases store plain-text passwords. verify() still accepts those, and
callers upgrade them to a hash as soon as they are seen (on login, or by
running upgrade_passwords.py).
"""
import hmac

from werkzeug.security import generate_password_hash, check_password_hash

_HASH_PREFIXES = ("scrypt:", "pbkdf2:")


def hash_password(password):
    return generate_password_hash(password)


def is_hashed(stored):
    return bool(stored) and stored.startswith(_HASH_PREFIXES)


def verify(stored, candidate):
    """True if candidate matches the stored password, hashed or legacy plain text."""
    if not stored:
        return False
    if is_hashed(stored):
        return check_password_hash(stored, candidate)
    return hmac.compare_digest(stored.encode("utf-8"), candidate.encode("utf-8"))

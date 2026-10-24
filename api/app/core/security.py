from pwdlib import PasswordHash

# Argon2 is the current recommended password hashing algorithm.
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)

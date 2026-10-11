from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    from pwdlib.exceptions import UnknownHashError
    try:
        return password_hash.verify(password, hashed_password)
    except (UnknownHashError, ValueError):
        return False

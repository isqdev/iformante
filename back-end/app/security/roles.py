from app.models.user import User


def is_admin(user: User | None) -> bool:
    return user is not None and user.role in {"ADMIN", "SUPER"}

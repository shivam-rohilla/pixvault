from flask_login import UserMixin


class User(UserMixin):
    """Thin wrapper around a Supabase users row, compatible with Flask-Login."""

    def __init__(self, data: dict):
        self.id = data["id"]
        self.username = data["username"]
        self.email = data["email"]
        self.password_hash = data.get("password_hash", "")
        self.is_admin = data.get("is_admin", False)
        self.storage_used = data.get("storage_used", 0)
        self.bio = data.get("bio", "")
        self.avatar_url = data.get("avatar_url", "")
        self.created_at = data.get("created_at", "")

    # Flask-Login expects get_id() to return a string
    def get_id(self) -> str:
        return str(self.id)

    @property
    def storage_used_mb(self) -> float:
        return round(self.storage_used / (1024 * 1024), 2)

    @property
    def storage_used_gb(self) -> float:
        return round(self.storage_used / (1024 * 1024 * 1024), 3)

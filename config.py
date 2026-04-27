import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # PostgreSQL (Supabase direct connection)
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    # Cloudinary
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

    # Max upload size: 100 MB
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "heic"}
    ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "webm", "mkv", "wmv"}

    @property
    def ALLOWED_EXTENSIONS(self):
        return self.ALLOWED_IMAGE_EXTENSIONS | self.ALLOWED_VIDEO_EXTENSIONS

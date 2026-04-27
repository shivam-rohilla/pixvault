from flask import Flask, render_template
from flask_login import LoginManager
from config import Config
from models import User
import db as database
import cloudinary


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── PostgreSQL connection pool (Supabase) ──────────────────
    database.init_pool(app.config["DATABASE_URL"])

    # ── Cloudinary ─────────────────────────────────────────────
    cloudinary.config(
        cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=app.config["CLOUDINARY_API_KEY"],
        api_secret=app.config["CLOUDINARY_API_SECRET"],
        secure=True,
    )

    # ── Flask-Login ────────────────────────────────────────────
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            row = database.query_one("SELECT * FROM users WHERE id = %s", (user_id,))
            return User(row) if row else None
        except Exception:
            return None

    # ── Blueprints ─────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.media import media_bp
    from routes.album import album_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(album_bp)
    app.register_blueprint(admin_bp)

    # ── Template filters ───────────────────────────────────────
    @app.template_filter("format_size")
    def format_size(size_bytes):
        if not size_bytes:
            return "0 B"
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    @app.template_filter("format_date")
    def format_date(date_str):
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y")
        except Exception:
            return date_str or ""

    # ── Error handlers ─────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

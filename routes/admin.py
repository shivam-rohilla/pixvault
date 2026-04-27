from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import db

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Admin access required.", "error")
            return redirect(url_for("media.index"))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    users = db.query_all("SELECT * FROM users ORDER BY created_at DESC")

    stats = db.query_one(
        """SELECT
               COUNT(*)                                            AS total_media,
               COUNT(*) FILTER (WHERE media_type = 'image')       AS image_count,
               COUNT(*) FILTER (WHERE media_type = 'video')       AS video_count,
               COALESCE(SUM(file_size), 0)                        AS total_storage
           FROM media"""
    )

    total_albums = db.query_one("SELECT COUNT(*) AS c FROM albums")["c"]

    recent_uploads = db.query_all(
        """SELECT m.id, m.original_filename, m.cloudinary_url, m.media_type,
                  m.file_size, m.created_at, u.username
           FROM media m JOIN users u ON m.user_id = u.id
           ORDER BY m.created_at DESC LIMIT 15"""
    )

    return render_template("admin.html",
                           users=users,
                           total_users=len(users),
                           total_media=stats["total_media"],
                           total_albums=total_albums,
                           total_storage=stats["total_storage"],
                           image_count=stats["image_count"],
                           video_count=stats["video_count"],
                           recent_uploads=recent_uploads)


@admin_bp.route("/admin/user/<user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    db.execute("DELETE FROM users WHERE id = %s", (user_id,))
    flash("User deleted.", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/user/<user_id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin(user_id):
    if user_id == current_user.id:
        flash("You cannot change your own admin status.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    row = db.query_one("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    if row:
        new_status = not row["is_admin"]
        db.execute("UPDATE users SET is_admin = %s WHERE id = %s", (new_status, user_id))
        flash(f"Admin {'granted' if new_status else 'revoked'}.", "success")

    return redirect(url_for("admin.admin_dashboard"))

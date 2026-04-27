import secrets
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify
)
from flask_login import login_required, current_user
import db

album_bp = Blueprint("album", __name__)


@album_bp.route("/albums")
@login_required
def albums():
    rows = db.query_all(
        """SELECT a.*,
                  COUNT(m.id) AS media_count,
                  (SELECT cloudinary_url FROM media
                   WHERE album_id = a.id ORDER BY created_at DESC LIMIT 1) AS cover
           FROM albums a
           LEFT JOIN media m ON m.album_id = a.id
           WHERE a.user_id = %s
           GROUP BY a.id
           ORDER BY a.created_at DESC""",
        (current_user.id,)
    )
    return render_template("albums.html", albums=rows)


@album_bp.route("/album/create", methods=["GET", "POST"])
@login_required
def create_album():
    if request.method == "POST":
        name        = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        is_public   = request.form.get("is_public") == "on"

        if not name:
            flash("Album name is required.", "error")
            return redirect(url_for("album.create_album"))

        row = db.execute_one(
            """INSERT INTO albums (user_id, name, description, is_public, share_token)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (current_user.id, name, description, is_public, secrets.token_urlsafe(32))
        )
        if row:
            flash(f'Album "{name}" created.', "success")
            return redirect(url_for("album.view_album", album_id=row["id"]))

        flash("Failed to create album.", "error")

    return render_template("create_album.html")


@album_bp.route("/album/<album_id>")
def view_album(album_id):
    album = db.query_one("SELECT * FROM albums WHERE id = %s", (album_id,))
    if not album:
        flash("Album not found.", "error")
        return redirect(url_for("media.dashboard"))

    is_owner = current_user.is_authenticated and current_user.id == album["user_id"]
    if not album["is_public"] and not is_owner:
        flash("This album is private.", "error")
        return redirect(url_for("media.index"))

    owner = db.query_one("SELECT username FROM users WHERE id = %s", (album["user_id"],))
    owner_username = owner["username"] if owner else "unknown"

    tag   = request.args.get("tag", "").strip()
    mtype = request.args.get("type", "").strip()

    clauses = ["album_id = %s"]
    params  = [album_id]
    if tag:
        clauses.append("%s = ANY(tags)");   params.append(tag)
    if mtype in ("image", "video"):
        clauses.append("media_type = %s");  params.append(mtype)

    media_items = db.query_all(
        "SELECT * FROM media WHERE " + " AND ".join(clauses) + " ORDER BY created_at DESC",
        params
    )

    # Collect unique tags used in this album for the filter bar
    tag_rows = db.query_all(
        "SELECT DISTINCT unnest(tags) AS tag FROM media WHERE album_id = %s ORDER BY tag",
        (album_id,)
    )
    all_tags = [r["tag"] for r in tag_rows]

    return render_template("album.html",
                           album=album, media_items=media_items,
                           owner_username=owner_username, is_owner=is_owner,
                           all_tags=all_tags, active_tag=tag, active_type=mtype)


@album_bp.route("/album/<album_id>/rename", methods=["POST"])
@login_required
def rename_album(album_id):
    new_name = request.form.get("name", "").strip()
    if not new_name:
        flash("Album name cannot be empty.", "error")
        return redirect(request.referrer or url_for("album.view_album", album_id=album_id))

    result = db.execute_one(
        "UPDATE albums SET name = %s WHERE id = %s AND user_id = %s RETURNING id",
        (new_name, album_id, current_user.id)
    )
    flash("Album renamed." if result else "Failed to rename album.", "success" if result else "error")
    return redirect(url_for("album.view_album", album_id=album_id))


@album_bp.route("/album/<album_id>/delete", methods=["POST"])
@login_required
def delete_album(album_id):
    db.execute("UPDATE media SET album_id = NULL WHERE album_id = %s AND user_id = %s",
               (album_id, current_user.id))
    db.execute("DELETE FROM albums WHERE id = %s AND user_id = %s",
               (album_id, current_user.id))
    flash("Album deleted. Media moved to Unsorted.", "success")
    return redirect(url_for("album.albums"))


@album_bp.route("/album/<album_id>/toggle-public", methods=["POST"])
@login_required
def toggle_public(album_id):
    row = db.query_one(
        "SELECT is_public FROM albums WHERE id = %s AND user_id = %s",
        (album_id, current_user.id)
    )
    if not row:
        return jsonify({"error": "Album not found"}), 404

    new_status = not row["is_public"]
    db.execute("UPDATE albums SET is_public = %s WHERE id = %s", (new_status, album_id))
    return jsonify({"is_public": new_status})


@album_bp.route("/share/album/<token>")
def share_album(token):
    album = db.query_one("SELECT * FROM albums WHERE share_token = %s", (token,))
    if not album:
        flash("Invalid share link.", "error")
        return redirect(url_for("media.index"))

    media_items    = db.query_all("SELECT * FROM media WHERE album_id = %s ORDER BY created_at DESC", (album["id"],))
    owner          = db.query_one("SELECT username FROM users WHERE id = %s", (album["user_id"],))
    owner_username = owner["username"] if owner else "unknown"

    return render_template("album.html",
                           album=album, media_items=media_items,
                           owner_username=owner_username, is_owner=False,
                           all_tags=[], active_tag="", active_type="")

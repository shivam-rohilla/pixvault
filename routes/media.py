import secrets
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify
)
from flask_login import login_required, current_user
import cloudinary
import cloudinary.uploader
import db

media_bp = Blueprint("media", __name__)

ALLOWED_IMAGE = {"png", "jpg", "jpeg", "gif", "webp", "svg", "heic"}
ALLOWED_VIDEO = {"mp4", "mov", "avi", "webm", "mkv", "wmv"}


def _ext(name): return name.rsplit(".", 1)[-1].lower() if "." in name else ""

def _mtype(name):
    e = _ext(name)
    if e in ALLOWED_IMAGE: return "image"
    if e in ALLOWED_VIDEO: return "video"
    return None

def _attach_album(item: dict) -> dict:
    """Lift aliased album_* columns into item['albums'] dict so templates work unchanged."""
    if item is None:
        return item
    album_name      = item.pop("album_name", None)
    album_is_public = item.pop("album_is_public", None)
    item["albums"]  = {"name": album_name, "is_public": album_is_public} if album_name is not None else None
    return item


# ── Landing page ───────────────────────────────────────────────
@media_bp.route("/")
def index():
    return render_template("index.html", showcase=[])


# ── Dashboard ──────────────────────────────────────────────────
@media_bp.route("/dashboard")
@login_required
def dashboard():
    media_items = db.query_all(
        "SELECT * FROM media WHERE user_id = %s ORDER BY created_at DESC",
        (current_user.id,)
    )
    albums = db.query_all(
        "SELECT * FROM albums WHERE user_id = %s ORDER BY created_at DESC",
        (current_user.id,)
    )
    image_count = sum(1 for m in media_items if m["media_type"] == "image")
    video_count = sum(1 for m in media_items if m["media_type"] == "video")
    return render_template("dashboard.html",
                           media_items=media_items, albums=albums,
                           image_count=image_count, video_count=video_count)


# ── Upload ─────────────────────────────────────────────────────
@media_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        if "file" not in request.files or not request.files["file"].filename:
            return jsonify({"error": "No file provided."}), 400

        file  = request.files["file"]
        mtype = _mtype(file.filename)
        if mtype is None:
            return jsonify({"error": "File type not supported."}), 400

        album_id = request.form.get("album_id") or None
        tags     = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]

        try:
            up = cloudinary.uploader.upload(file, resource_type="auto", folder="pixvault")

            row = db.execute_one(
                """INSERT INTO media
                   (user_id, album_id, filename, original_filename, cloudinary_public_id,
                    cloudinary_url, media_type, file_size, width, height, duration, tags, share_token)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (current_user.id, album_id, file.filename, file.filename,
                 up["public_id"], up["secure_url"], mtype,
                 up.get("bytes", 0), up.get("width"), up.get("height"), up.get("duration"),
                 tags, secrets.token_urlsafe(32))
            )

            new_used = current_user.storage_used + up.get("bytes", 0)
            db.execute("UPDATE users SET storage_used = %s WHERE id = %s",
                       (new_used, current_user.id))

            return jsonify({"success": True, "media": row})

        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    albums = db.query_all(
        "SELECT * FROM albums WHERE user_id = %s ORDER BY name", (current_user.id,)
    )
    return render_template("upload.html", albums=albums)


# ── Media detail ───────────────────────────────────────────────
@media_bp.route("/media/<media_id>")
def media_detail(media_id):
    item = db.query_one(
        """SELECT m.*, a.name AS album_name, a.is_public AS album_is_public
           FROM media m LEFT JOIN albums a ON m.album_id = a.id
           WHERE m.id = %s""",
        (media_id,)
    )
    if not item:
        flash("Media not found.", "error")
        return redirect(url_for("media.index"))

    _attach_album(item)

    is_owner     = current_user.is_authenticated and current_user.id == item["user_id"]
    album_public = item.get("albums") and item["albums"].get("is_public")
    if not is_owner and not album_public:
        flash("This media is private.", "error")
        return redirect(url_for("media.index"))

    owner = db.query_one("SELECT username FROM users WHERE id = %s", (item["user_id"],))
    owner_username = owner["username"] if owner else "unknown"

    move_albums = []
    if is_owner:
        move_albums = db.query_all(
            "SELECT id, name FROM albums WHERE user_id = %s ORDER BY name", (current_user.id,)
        )

    return render_template("media_detail.html", item=item,
                           owner_username=owner_username,
                           move_albums=move_albums, is_owner=is_owner)


# ── Delete ─────────────────────────────────────────────────────
@media_bp.route("/media/<media_id>/delete", methods=["POST"])
@login_required
def delete_media(media_id):
    item = db.query_one(
        "SELECT * FROM media WHERE id = %s AND user_id = %s", (media_id, current_user.id)
    )
    if not item:
        flash("Media not found or access denied.", "error")
        return redirect(url_for("media.dashboard"))

    try:
        cloudinary.uploader.destroy(item["cloudinary_public_id"], resource_type=item["media_type"])
    except Exception:
        pass

    new_used = max(0, current_user.storage_used - item.get("file_size", 0))
    db.execute("UPDATE users SET storage_used = %s WHERE id = %s", (new_used, current_user.id))
    db.execute("DELETE FROM media WHERE id = %s", (media_id,))

    flash("Media deleted.", "success")
    return redirect(request.form.get("next") or url_for("media.dashboard"))


# ── Move ───────────────────────────────────────────────────────
@media_bp.route("/media/<media_id>/move", methods=["POST"])
@login_required
def move_media(media_id):
    album_id = request.form.get("album_id") or None
    db.execute(
        "UPDATE media SET album_id = %s WHERE id = %s AND user_id = %s",
        (album_id, media_id, current_user.id)
    )
    flash("Media moved.", "success")
    return redirect(request.referrer or url_for("media.dashboard"))


# ── Tags ───────────────────────────────────────────────────────
@media_bp.route("/media/<media_id>/tags", methods=["POST"])
@login_required
def update_tags(media_id):
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    db.execute(
        "UPDATE media SET tags = %s WHERE id = %s AND user_id = %s",
        (tags, media_id, current_user.id)
    )
    flash("Tags updated.", "success")
    return redirect(request.referrer or url_for("media.media_detail", media_id=media_id))


# ── Download ───────────────────────────────────────────────────
@media_bp.route("/download/<media_id>")
def download_media(media_id):
    item = db.query_one(
        """SELECT m.*, a.is_public AS album_is_public
           FROM media m LEFT JOIN albums a ON m.album_id = a.id
           WHERE m.id = %s""",
        (media_id,)
    )
    if not item:
        flash("Media not found.", "error")
        return redirect(url_for("media.index"))

    is_owner     = current_user.is_authenticated and current_user.id == item["user_id"]
    album_public = item.get("album_is_public")
    if not is_owner and not album_public:
        flash("Access denied.", "error")
        return redirect(url_for("media.index"))

    dl_url = item["cloudinary_url"].replace("/upload/", "/upload/fl_attachment/")
    return redirect(dl_url)


# ── Share link ─────────────────────────────────────────────────
@media_bp.route("/share/media/<token>")
def share_media(token):
    item = db.query_one(
        """SELECT m.*, a.name AS album_name, a.is_public AS album_is_public
           FROM media m LEFT JOIN albums a ON m.album_id = a.id
           WHERE m.share_token = %s""",
        (token,)
    )
    if not item:
        flash("Invalid share link.", "error")
        return redirect(url_for("media.index"))

    _attach_album(item)
    owner = db.query_one("SELECT username FROM users WHERE id = %s", (item["user_id"],))
    owner_username = owner["username"] if owner else "unknown"

    return render_template("media_detail.html", item=item,
                           owner_username=owner_username,
                           move_albums=[], is_owner=False)


# ── Search ─────────────────────────────────────────────────────
@media_bp.route("/search")
@login_required
def search():
    q        = request.args.get("q", "").strip()
    tag      = request.args.get("tag", "").strip()
    album_id = request.args.get("album", "").strip()
    mtype    = request.args.get("type", "").strip()

    clauses = ["user_id = %s"]
    params  = [current_user.id]

    if q:
        clauses.append("original_filename ILIKE %s");  params.append(f"%{q}%")
    if tag:
        clauses.append("%s = ANY(tags)");               params.append(tag)
    if album_id:
        clauses.append("album_id = %s");                params.append(album_id)
    if mtype in ("image", "video"):
        clauses.append("media_type = %s");              params.append(mtype)

    sql = "SELECT * FROM media WHERE " + " AND ".join(clauses) + " ORDER BY created_at DESC"
    results = db.query_all(sql, params)
    albums  = db.query_all("SELECT id, name FROM albums WHERE user_id = %s ORDER BY name", (current_user.id,))

    return render_template("search.html", media_items=results, albums=albums,
                           q=q, tag=tag, album_id=album_id, mtype=mtype)


# ── Public portfolio ───────────────────────────────────────────
@media_bp.route("/u/<username>")
def portfolio(username):
    portfolio_user = db.query_one(
        "SELECT id, username, bio, avatar_url, created_at FROM users WHERE username = %s",
        (username,)
    )
    if not portfolio_user:
        flash("User not found.", "error")
        return redirect(url_for("media.index"))

    uid = portfolio_user["id"]
    pub_albums = db.query_all(
        "SELECT * FROM albums WHERE user_id = %s AND is_public = TRUE ORDER BY created_at DESC",
        (uid,)
    )
    pub_media = []
    if pub_albums:
        ids = [a["id"] for a in pub_albums]
        pub_media = db.query_all(
            "SELECT * FROM media WHERE album_id = ANY(%s) ORDER BY created_at DESC", (ids,)
        )

    return render_template("portfolio.html", portfolio_user=portfolio_user,
                           albums=pub_albums, media_items=pub_media)

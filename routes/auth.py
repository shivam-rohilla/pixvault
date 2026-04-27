from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt
import db
from models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("media.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")
        if len(username) < 3 or len(username) > 30:
            flash("Username must be 3–30 characters.", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        if db.query_one("SELECT id FROM users WHERE username = %s", (username,)):
            flash("That username is already taken.", "error")
            return render_template("register.html")
        if db.query_one("SELECT id FROM users WHERE email = %s", (email,)):
            flash("An account with that email already exists.", "error")
            return render_template("register.html")

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        row = db.execute_one(
            """INSERT INTO users (username, email, password_hash, is_admin, storage_used)
               VALUES (%s, %s, %s, FALSE, 0) RETURNING *""",
            (username, email, pw_hash),
        )
        if row:
            login_user(User(row))
            flash(f"Welcome to Pixvault, {username}!", "success")
            return redirect(url_for("media.dashboard"))

        flash("Registration failed. Please try again.", "error")

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("media.dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        row = db.query_one("SELECT * FROM users WHERE email = %s", (email,))
        if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            login_user(User(row), remember=remember)
            return redirect(request.args.get("next") or url_for("media.dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been signed out.", "info")
    return redirect(url_for("media.index"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        bio          = request.form.get("bio", "").strip()
        new_password = request.form.get("new_password", "")
        cur_password = request.form.get("current_password", "")

        updates = {"bio": bio}

        if new_password:
            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "error")
                return redirect(url_for("auth.profile"))
            row = db.query_one("SELECT password_hash FROM users WHERE id = %s", (current_user.id,))
            if not row or not bcrypt.checkpw(cur_password.encode(), row["password_hash"].encode()):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("auth.profile"))
            updates["password_hash"] = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

        set_clause = ", ".join(f"{k} = %s" for k in updates)
        db.execute(
            f"UPDATE users SET {set_clause} WHERE id = %s",
            (*updates.values(), current_user.id),
        )
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))

    media_count = db.query_one("SELECT COUNT(*) AS c FROM media WHERE user_id = %s", (current_user.id,))["c"]
    album_count = db.query_one("SELECT COUNT(*) AS c FROM albums WHERE user_id = %s", (current_user.id,))["c"]
    return render_template("profile.html", media_count=media_count, album_count=album_count)

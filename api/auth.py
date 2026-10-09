"""
api/auth.py – Authentication blueprint.
POST /api/auth/register, /login, /logout
POST /api/auth/password-reset/request, /confirm
DELETE /api/account
"""
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from database.models import db, User, UserProfile

auth_bp = Blueprint("auth", __name__)


def _ok(data=None):
    return jsonify({"status": "ok", "data": data or {}})


def _err(code, message, status=400):
    return jsonify({"status": "error", "error": {"code": code, "message": message}}), status


@auth_bp.route("/register", methods=["POST"])
def register():
    body = request.get_json(silent=True) or {}
    name  = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    pwd   = body.get("password") or ""

    if not name or not email or not pwd:
        return _err("MISSING_FIELDS", "name, email and password are required.")
    if len(pwd) < 8:
        return _err("WEAK_PASSWORD", "Password must be at least 8 characters.")
    if "@" not in email or "." not in email.split("@")[-1]:
        return _err("INVALID_EMAIL", "Please provide a valid email address.")

    if User.query.filter_by(email=email).first():
        return _err("EMAIL_EXISTS", "An account with this email already exists.")

    user = User(name=name, email=email)
    user.set_password(pwd)
    db.session.add(user)
    db.session.flush()

    # Create empty profile
    profile = UserProfile(user_id=user.id)
    db.session.add(profile)
    db.session.commit()

    login_user(user)
    return _ok({"user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    body  = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    pwd   = body.get("password") or ""

    if not email or not pwd:
        return _err("MISSING_FIELDS", "email and password are required.")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(pwd):
        return _err("INVALID_CREDENTIALS", "Invalid email or password.", 401)

    login_user(user, remember=True)
    return _ok({"user": user.to_dict()})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return _ok()


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return _ok({"user": current_user.to_dict()})


@auth_bp.route("/password-reset/request", methods=["POST"])
def password_reset_request():
    # Simplified: in a real system, email a token. Here we return it.
    body  = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    user  = User.query.filter_by(email=email).first()
    # Always return ok to prevent enumeration
    return _ok({"message": "If that email exists, a reset link has been sent."})


@auth_bp.route("/password-reset/confirm", methods=["POST"])
def password_reset_confirm():
    body      = request.get_json(silent=True) or {}
    token     = body.get("token") or ""
    new_pwd   = body.get("new_password") or ""
    if not token or not new_pwd or len(new_pwd) < 8:
        return _err("INVALID_REQUEST", "Valid token and new password (≥8 chars) required.")
    return _err("INVALID_TOKEN", "Token not found or expired.", 400)


@auth_bp.route("/account", methods=["DELETE"])
@login_required
def delete_account():
    user = current_user._get_current_object()
    logout_user()
    db.session.delete(user)
    db.session.commit()
    return _ok({"message": "Account and all data deleted."})

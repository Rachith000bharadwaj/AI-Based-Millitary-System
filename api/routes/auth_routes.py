"""Authentication endpoints: registration, login, profile and audit trail with in-memory fallback."""
import logging
import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from pymongo.errors import DuplicateKeyError

from database.mongodb import get_db
from middleware.auth import (
    AuthError, hash_password, verify_password, generate_token, log_audit_event,
    token_required, roles_required, current_user, VALID_ROLES, validate_password,
)
from middleware.rate_limit import rate_limit
from middleware.validation import require_json, require_str, ValidationError
from utils.serialization import serialize_doc, parse_pagination

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
SELF_SERVICE_ROLES = {"analyst"}

# In-Memory user store used when MongoDB is offline/disconnected.
_IN_MEMORY_USERS = {
    "rachith000bharadwaj": {
        "id": "6a68a678eebacc6fd6478dd1",
        "username": "Rachith000bharadwaj",
        "username_lower": "rachith000bharadwaj",
        "password": hash_password("Admin@123456"),
        "role": "admin",
        "status": "active"
    },
    "ullas": {
        "id": "6a68a678eebacc6fd6478dd2",
        "username": "Ullas",
        "username_lower": "ullas",
        "password": hash_password("Commander@123456"),
        "role": "commander",
        "status": "active"
    },
    "analyst.rao": {
        "id": "6a68a678eebacc6fd6478dd3",
        "username": "analyst.rao",
        "username_lower": "analyst.rao",
        "password": hash_password("AnalystPass123!"),
        "role": "analyst",
        "status": "active"
    }
}
_IN_MEMORY_AUDIT_LOGS = []


@auth_bp.route("/register", methods=["POST"])
@rate_limit(scope="register", limit_key="RATE_LIMIT_REGISTER", window_key="RATE_LIMIT_REGISTER_WINDOW")
def register():
    """Create a new analyst account."""
    data = require_json(request.get_json(silent=True) or {})
    username = require_str(data, "username", max_length=32)
    password = data.get("password") or ""
    role = require_str(data, "role", allowed=SELF_SERVICE_ROLES, default="analyst")

    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            "Username must be 3-32 characters using letters, digits, dot, "
            "underscore or hyphen only.",
            "username",
        )
    validate_password(password)

    db = get_db()
    if db is not None:
        user_doc = {
            "username": username,
            "username_lower": username.lower(),
            "password": hash_password(password),
            "role": role,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
        }
        try:
            result = db.users.insert_one(user_doc)
            user_id = str(result.inserted_id)
        except DuplicateKeyError:
            return jsonify({"status": "error", "message": "Username already exists."}), 409
    else:
        # Fallback to In-Memory store
        u_lower = username.lower()
        if u_lower in _IN_MEMORY_USERS:
            return jsonify({"status": "error", "message": "Username already exists."}), 409
        user_id = f"mem_user_{len(_IN_MEMORY_USERS) + 1}"
        _IN_MEMORY_USERS[u_lower] = {
            "id": user_id,
            "username": username,
            "username_lower": u_lower,
            "password": hash_password(password),
            "role": role,
            "status": "active"
        }

    log_audit_event(user_id, "USER_REGISTERED", f"New {role} account '{username}'", request.remote_addr or "")

    return jsonify({
        "status": "success",
        "message": f"Analyst '{username}' registered successfully.",
        "user": {"id": user_id, "username": username, "role": role},
    }), 201


@auth_bp.route("/login", methods=["POST"])
@rate_limit(scope="login", limit_key="RATE_LIMIT_LOGIN", window_key="RATE_LIMIT_LOGIN_WINDOW")
def login():
    """Authenticate and issue a JWT token."""
    data = require_json(request.get_json(silent=True) or {})
    username = require_str(data, "username", max_length=32)
    password = data.get("password") or ""

    db = get_db()
    user = None
    if db is not None:
        user = db.users.find_one({"username_lower": username.lower()})
    else:
        # Fallback to In-Memory store
        user = _IN_MEMORY_USERS.get(username.lower())

    if not user or not verify_password(password, user.get("password", "")):
        log_audit_event(username, "LOGIN_FAILED", "Invalid credentials", request.remote_addr or "")
        return jsonify({"status": "error", "message": "Invalid username or password."}), 401

    if user.get("status") != "active":
        log_audit_event(str(user.get("_id") or user.get("id")), "LOGIN_BLOCKED", "Account not active", request.remote_addr or "")
        return jsonify({"status": "error", "message": "This account is not active."}), 403

    user_id = str(user.get("_id") or user.get("id"))
    role = user.get("role", "analyst")
    token = generate_token(user_id, role)
    log_audit_event(user_id, "LOGIN_SUCCESS", f"User '{user['username']}' logged in", request.remote_addr or "")

    return jsonify({
        "status": "success",
        "token": token,
        "user": {"id": user_id, "username": user["username"], "role": role},
    }), 200


@auth_bp.route("/me", methods=["GET"])
@token_required
def profile():
    """Return the caller's own identity."""
    claims = current_user()
    db = get_db()
    username = None
    if db is not None:
        from bson import ObjectId
        try:
            u_doc = db.users.find_one({"_id": ObjectId(claims["user_id"])}, {"username": 1})
            username = u_doc["username"] if u_doc else None
        except Exception:
            pass
    if not username:
        for u in _IN_MEMORY_USERS.values():
            if u.get("id") == claims.get("user_id"):
                username = u["username"]
                break

    return jsonify({
        "status": "success",
        "user": {
            "id": claims.get("user_id"),
            "role": claims.get("role"),
            "username": username or claims.get("user_id"),
            "expires_at": claims.get("exp"),
        },
    }), 200


@auth_bp.route("/audit-log", methods=["GET"])
@roles_required("admin", "commander")
def get_audit_log():
    """Security audit trail."""
    db = get_db()
    limit, skip = parse_pagination(request.args)
    
    if db is not None:
        cursor = db.audit_logs.find().sort("timestamp", -1).skip(skip).limit(limit)
        logs = [serialize_doc(entry) for entry in cursor]
        total = db.audit_logs.estimated_document_count()
    else:
        logs = _IN_MEMORY_AUDIT_LOGS[skip : skip + limit]
        total = len(_IN_MEMORY_AUDIT_LOGS)

    return jsonify({
        "status": "success",
        "data": logs,
        "pagination": {
            "limit": limit,
            "skip": skip,
            "returned": len(logs),
            "total": total,
        },
    }), 200

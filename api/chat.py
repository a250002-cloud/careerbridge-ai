"""
api/chat.py – AI Career Copilot.
POST /api/chat/message
GET  /api/chat/history
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from database.models import db, ChatSession, ChatMessage
from services.chatbot import handle_message

chat_bp = Blueprint("chat", __name__)


def _ok(data=None):
    return jsonify({"status": "ok", "data": data or {}})

def _err(code, msg, status=400):
    return jsonify({"status": "error", "error": {"code": code, "message": msg}}), status


@chat_bp.route("/message", methods=["POST"])
@login_required
def message():
    body = request.get_json(silent=True) or {}
    user_message = (body.get("message") or "").strip()
    session_id   = body.get("session_id")

    if not user_message:
        return _err("MISSING_MESSAGE", "message is required.")
    if len(user_message) > 2000:
        return _err("MESSAGE_TOO_LONG", "Message must be under 2000 characters.")

    result = handle_message(current_user.id, session_id, user_message)
    return _ok(result)


@chat_bp.route("/history", methods=["GET"])
@login_required
def history():
    session_id = request.args.get("session_id", type=int)

    if session_id:
        session = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first()
        if not session:
            return _err("NOT_FOUND", "Session not found.", 404)
        messages = [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in session.messages
        ]
        return _ok({"session_id": session_id, "messages": messages})

    # Return list of sessions
    sessions = ChatSession.query.filter_by(user_id=current_user.id)\
        .order_by(ChatSession.created_at.desc()).limit(20).all()
    return _ok({
        "sessions": [
            {
                "session_id": s.id,
                "created_at": s.created_at.isoformat(),
                "message_count": len(s.messages),
                "last_message": s.messages[-1].content[:80] if s.messages else "",
            }
            for s in sessions
        ]
    })

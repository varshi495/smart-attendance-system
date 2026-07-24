"""
app.py - Flask web server and route definitions
Smart Attendance System with Facial Recognition

Run:
    python app.py

Then open:
    http://localhost:5000
"""

import os
import math
import logging
import threading
import uuid
from datetime import date
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, flash, send_file, session
)
from werkzeug.utils import secure_filename

# ── College Location Constants ───────────────────────────────────────────────
COLLEGE_LAT = 13.133106  # Placeholder: Replace with actual college latitude
COLLEGE_LNG = 77.568456  # Placeholder: Replace with actual college longitude

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371e3  # Earth radius in meters
    phi1 = lat1 * math.pi / 180
    phi2 = lat2 * math.pi / 180
    delta_phi = (lat2 - lat1) * math.pi / 180
    delta_lambda = (lon2 - lon1) * math.pi / 180

    a = math.sin(delta_phi / 2) * math.sin(delta_phi / 2) + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) * math.sin(delta_lambda / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

# ── Local modules ────────────────────────────────────────────────────────────
import config
from config import (
    SECRET_KEY, DEBUG, PORT, KNOWN_FACES_DIR,
    CSV_PATH, EXCEL_PATH
)
from database import (
    init_db, register_user, get_all_users,
    get_user_count, get_today_count, get_recent_activity,
    get_attendance_logs, get_user_by_id, delete_user,
    is_already_marked
)
from face_engine import (
    encode_face_from_file, encode_face_from_base64,
    recognize_faces_in_frame, draw_face_boxes,
    base64_to_frame, frame_to_base64
)
from attendance import (
    mark_present, export_to_csv, export_to_excel,
    get_monthly_summary, get_attendance_rate
)
from notifications import (
    notify_attendance, load_notification_settings,
    test_email, test_sms
)
from database import (
    get_notification_settings, save_notification_settings
)

# ── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ── Flask App ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024   # 16 MB upload limit

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

# ── In-memory cache for known face encodings ─────────────────────────────────
# Reloaded whenever a new user is registered
_known_faces_cache = {
    "encodings": [],
    "names":     [],
    "ids":       [],
}
_cache_lock = threading.Lock()


def reload_known_faces():
    """Reload all registered face encodings from the database into memory."""
    users = get_all_users()
    encodings, names, ids = [], [], []

    for u in users:
        if u["encoding"] is not None:
            encodings.append(u["encoding"])
            names.append(u["name"])
            ids.append(u["user_id"])

    with _cache_lock:
        _known_faces_cache["encodings"] = encodings
        _known_faces_cache["names"]     = names
        _known_faces_cache["ids"]       = ids

    logger.info("Loaded %d known face(s) into cache", len(encodings))


def allowed_file(filename: str) -> bool:
    """Check if an uploaded file has an allowed image extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ════════════════════════════════════════════════════════════════════════════
#  ROUTES — Pages
# ════════════════════════════════════════════════════════════════════════════

@app.route("/")
def dashboard():
    """Main dashboard showing stats and recent activity."""
    stats = {
        "total_users":   get_user_count(),
        "today_present": get_today_count(),
        "today_date":    date.today().strftime("%B %d, %Y"),
        "attendance_rate": get_attendance_rate(),
    }
    recent = get_recent_activity(limit=8)
    return render_template("index.html", stats=stats, recent=recent)


@app.route("/register", methods=["GET"])
def register_page():
    """User registration page."""
    return render_template("register.html")


@app.route("/attendance")
def attendance_page():
    """Live webcam attendance page."""
    return render_template("attendance.html")


@app.route("/report")
def report_page():
    """Attendance log viewer and export page."""
    filter_date = request.args.get("date", "")
    filter_name = request.args.get("name", "")
    logs = get_attendance_logs(
        filter_date=filter_date or None,
        filter_name=filter_name or None
    )
    summary = get_monthly_summary()
    return render_template("report.html", logs=logs, summary=summary,
                           filter_date=filter_date, filter_name=filter_name)


@app.route("/settings")
def settings_page():
    """Notification settings page (email + SMS configuration)."""
    cfg = get_notification_settings()
    return render_template("settings.html", cfg=cfg)


# ════════════════════════════════════════════════════════════════════════════
#  ROUTES — API Endpoints
# ════════════════════════════════════════════════════════════════════════════


@app.route("/api/register", methods=["POST"])
def api_register():
    """
    Register a new user.

    Accepts multipart form data with:
      - name       (str) required
      - user_id    (str) required
      - department (str) optional
      - photo      (file) OR
      - photo_b64  (str base64) from webcam capture
    """
    name       = request.form.get("name", "").strip()
    user_id    = request.form.get("user_id", "").strip().upper()
    department = request.form.get("department", "").strip()

    # Validate required fields
    if not name or not user_id:
        return jsonify({"success": False, "message": "Name and ID are required"}), 400

    # Check for duplicate user_id
    if get_user_by_id(user_id):
        return jsonify({"success": False, "message": f"User ID '{user_id}' is already registered"}), 400

    encoding    = None
    photo_path  = ""

    # ── Option A: File Upload ────────────────────────────────────────────────
    if "photo" in request.files and request.files["photo"].filename:
        photo_file = request.files["photo"]

        if not allowed_file(photo_file.filename):
            return jsonify({"success": False, "message": "Invalid file type. Use JPG/PNG"}), 400

        filename   = secure_filename(f"{user_id}_{name.replace(' ', '_')}.jpg")
        photo_path = os.path.join(KNOWN_FACES_DIR, filename)
        photo_file.save(photo_path)

        encoding = encode_face_from_file(photo_path)

    # ── Option B: Base64 Webcam Capture ──────────────────────────────────────
    elif "photo_b64" in request.form and request.form["photo_b64"]:
        b64_data   = request.form["photo_b64"]
        encoding   = encode_face_from_base64(b64_data)

        if encoding is not None:
            # Save the webcam image as a file too
            import base64, cv2
            import numpy as np
            from PIL import Image
            from io import BytesIO
            if "," in b64_data:
                b64_data = b64_data.split(",")[1]
            img_bytes  = base64.b64decode(b64_data)
            pil_img    = Image.open(BytesIO(img_bytes))
            filename   = f"{user_id}_{name.replace(' ', '_')}.jpg"
            photo_path = os.path.join(KNOWN_FACES_DIR, filename)
            pil_img.save(photo_path)

    else:
        return jsonify({"success": False, "message": "Please provide a photo"}), 400

    # ── Validate face found ──────────────────────────────────────────────────
    if encoding is None:
        # Clean up saved file if encoding failed
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        return jsonify({
            "success": False,
            "message": "No face detected in the photo. Please try a clearer image."
        }), 400

    # ── Save to database ──────────────────────────────────────────────────────
    success = register_user(user_id, name, department, photo_path, encoding)

    if success:
        # Refresh in-memory face cache
        reload_known_faces()
        return jsonify({
            "success": True,
            "message": f"✅ {name} registered successfully!",
            "user_id": user_id,
        })
    else:
        return jsonify({
            "success": False,
            "message": "Registration failed. User ID may already exist."
        }), 400


@app.route("/api/recognize", methods=["POST"])
def api_recognize():
    """
    Recognize faces in a frame and mark attendance.

    Accepts JSON: { "frame": "<base64 image string>" }

    Returns JSON with recognized faces and attendance results.
    """
    data   = request.get_json(force=True)
    b64img = data.get("frame", "")

    if not b64img:
        return jsonify({"success": False, "message": "No frame provided"}), 400

    # Decode base64 frame to BGR numpy array
    frame = base64_to_frame(b64img)
    if frame is None:
        return jsonify({"success": False, "message": "Invalid image data"}), 400

    # Get current known face cache
    with _cache_lock:
        encodings = _known_faces_cache["encodings"][:]
        names     = _known_faces_cache["names"][:]
        ids       = _known_faces_cache["ids"][:]

    # Perform face recognition
    results = recognize_faces_in_frame(frame, encodings, names, ids)

    # Evaluate attendance logic without marking
    attendance_results = []
    for r in results:
        if r["name"] != "Unknown" and r["user_id"] and r["is_live"]:
            already_marked = is_already_marked(r["user_id"], date.today().isoformat())
            attendance_results.append({
                "user_id":        r["user_id"],
                "name":           r["name"],
                "confidence":     r["confidence"],
                "is_live":        r["is_live"],
                "already_marked": already_marked,
                "message":        "Location verification required" if not already_marked else f"{r['name']} already marked for today",
            })
        elif r["name"] != "Unknown" and not r["is_live"]:
            attendance_results.append({
                "user_id":    r["user_id"],
                "name":       r["name"],
                "confidence": r["confidence"],
                "is_live":    False,
                "message":    "⚠ Possible spoof detected — attendance NOT marked",
            })

    # Return face coordinates for client-side drawing (no heavy image encoding)
    faces = []
    for r in results:
        faces.append({
            "top": r["top"], "right": r["right"],
            "bottom": r["bottom"], "left": r["left"],
            "name": r["name"], "confidence": r["confidence"],
            "is_live": r["is_live"],
        })

    return jsonify({
        "success":    True,
        "faces_found": len(results),
        "faces":      faces,
        "attendance": attendance_results,
    })


@app.route("/api/verify_location_and_mark", methods=["POST"])
def api_verify_location_and_mark():
    """
    Verify location and mark attendance if within 100 meters.
    """
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    name = data.get("name")
    lat = data.get("lat")
    lng = data.get("lng")

    if not all([user_id, name, lat is not None, lng is not None]):
        return jsonify({"success": False, "message": "Missing required data"}), 400

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid coordinates"}), 400

    distance = calculate_distance(lat, lng, COLLEGE_LAT, COLLEGE_LNG)
    
    if distance <= 700:
        att = mark_present(user_id, name, lat=lat, lng=lng, verified=True)
        if att.get("success") and not att.get("already_marked"):
            user_info = get_user_by_id(user_id)
            dept = user_info.get("department", "") if user_info else ""
            notify_attendance(name, user_id, dept)
        
        return jsonify({
            "success": True, 
            "message": "Attendance Marked Successfully", 
            "already_marked": att.get("already_marked", False),
            "time": att.get("time", "")
        })
    else:
        # Mark as failed in DB
        mark_present(user_id, name, lat=lat, lng=lng, verified=False, status="Failed - Outside Campus")
        return jsonify({"success": False, "message": "You are outside the college campus"}), 400


@app.route("/api/stats")
def api_stats():
    """Return dashboard statistics as JSON."""
    return jsonify({
        "total_users":      get_user_count(),
        "today_present":    get_today_count(),
        "attendance_rate":  get_attendance_rate(),
        "today_date":       date.today().strftime("%B %d, %Y"),
        "monthly_summary":  get_monthly_summary(),
    })


@app.route("/api/users")
def api_users():
    """Return list of all registered users (without encodings)."""
    users = get_all_users()
    # Strip encoding blob before sending to client
    safe_users = [
        {k: v for k, v in u.items() if k != "encoding"}
        for u in users
    ]
    return jsonify({"success": True, "users": safe_users})


@app.route("/api/users/<user_id>", methods=["DELETE"])
def api_delete_user(user_id):
    """Delete a registered user and their attendance records."""
    success = delete_user(user_id)
    if success:
        reload_known_faces()   # Refresh cache
        return jsonify({"success": True, "message": f"User {user_id} deleted"})
    return jsonify({"success": False, "message": "Delete failed"}), 400


@app.route("/api/attendance")
def api_attendance():
    """Return attendance logs as JSON with optional filters."""
    filter_date = request.args.get("date")
    filter_name = request.args.get("name")
    logs = get_attendance_logs(filter_date=filter_date, filter_name=filter_name)
    return jsonify({"success": True, "logs": logs, "count": len(logs)})


@app.route("/api/export/csv")
def api_export_csv():
    """Generate and download attendance CSV."""
    filter_date = request.args.get("date")
    filter_name = request.args.get("name")
    path = export_to_csv(filter_date=filter_date, filter_name=filter_name)
    return send_file(path, as_attachment=True, download_name="attendance_report.csv")


@app.route("/api/export/excel")
def api_export_excel():
    """Generate and download attendance Excel file."""
    filter_date = request.args.get("date")
    filter_name = request.args.get("name")
    path = export_to_excel(filter_date=filter_date, filter_name=filter_name)
    return send_file(
        path, as_attachment=True,
        download_name="attendance_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ════════════════════════════════════════════════════════════════════════════
#  ROUTES — Notification Settings
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/settings/notifications", methods=["POST"])
def api_save_notification_settings():
    """
    Save email and SMS notification settings.

    Accepts JSON body with any subset of these keys:
      email_enabled, smtp_host, smtp_port, sender_email,
      sender_pass, recipient_email,
      sms_enabled, twilio_sid, twilio_token, twilio_from, twilio_to
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    # Allowed keys only — prevent arbitrary DB writes
    allowed_keys = {
        "email_enabled", "smtp_host", "smtp_port", "sender_email",
        "sender_pass", "recipient_email",
        "sms_enabled", "twilio_sid", "twilio_token", "twilio_from", "twilio_to",
    }
    filtered = {k: v for k, v in data.items() if k in allowed_keys}

    ok = save_notification_settings(filtered)
    if not ok:
        return jsonify({"success": False, "message": "Failed to save settings"}), 500

    # Reload live config in notifications module
    load_notification_settings(get_notification_settings())

    return jsonify({"success": True, "message": "✅ Settings saved successfully!"})


@app.route("/api/settings/test-email", methods=["POST"])
def api_test_email():
    """Send a test email using the currently saved settings."""
    result = test_email()
    return jsonify(result)


@app.route("/api/settings/test-sms", methods=["POST"])
def api_test_sms():
    """Send a test SMS using the currently saved settings."""
    result = test_sms()
    return jsonify(result)


# ════════════════════════════════════════════════════════════════════════════
#  Startup
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Initialize database schema
    init_db()

    # Load registered faces into memory
    reload_known_faces()

    # Load notification settings from DB into the notifications module
    load_notification_settings(get_notification_settings())

    logger.info("=" * 50)
    logger.info("  Smart Attendance System starting...")
    logger.info("  Open: http://localhost:%d", PORT)
    logger.info("=" * 50)

    app.run(debug=DEBUG, port=PORT, threaded=True)

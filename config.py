"""
config.py - Application-wide configuration constants
Smart Attendance System with Facial Recognition
"""

import os

# ── Base Paths ──────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
DATA_DIR        = os.path.join(BASE_DIR, "data")
KNOWN_FACES_DIR = os.path.join(BASE_DIR, "known_faces")

# ── Database ────────────────────────────────────────────────────────────────
DB_PATH         = os.path.join(DATA_DIR, "attendance.db")

# ── Export Files ────────────────────────────────────────────────────────────
CSV_PATH        = os.path.join(DATA_DIR, "attendance.csv")
EXCEL_PATH      = os.path.join(DATA_DIR, "attendance.xlsx")

# ── Face Recognition Settings ───────────────────────────────────────────────
# Lower tolerance = stricter matching (0.4–0.6 recommended)
FACE_TOLERANCE  = 0.5

# Minimum face confidence for recognition (0.0–1.0)
MIN_CONFIDENCE  = 0.55

# Number of jitters when encoding (higher = more accurate but slower)
NUM_JITTERS     = 1

# ── Webcam Settings ─────────────────────────────────────────────────────────
FRAME_WIDTH     = 640
FRAME_HEIGHT    = 480

# ── Session Settings ─────────────────────────────────────────────────────────
# Seconds to wait before marking the same person again in one session
RECHECK_DELAY   = 30

# ── Flask Settings ───────────────────────────────────────────────────────────
SECRET_KEY      = "smart_attendance_secret_2024"
DEBUG           = True
PORT            = 5000

# ── Liveness Detection ───────────────────────────────────────────────────────
# Threshold for LBP texture variance to distinguish real face vs photo
LIVENESS_THRESHOLD = 50.0

# Ensure required directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

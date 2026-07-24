"""
face_engine.py - Face detection, encoding, and recognition engine
Smart Attendance System with Facial Recognition

Uses:
  - face_recognition  (dlib-based 128-d embeddings)
  - OpenCV            (image preprocessing, CLAHE, LBP)
  - NumPy             (array math)
"""

import cv2
import numpy as np
import face_recognition
import logging
import os
import base64
from io import BytesIO
from typing import Optional
from PIL import Image
from config import FACE_TOLERANCE, MIN_CONFIDENCE, NUM_JITTERS, LIVENESS_THRESHOLD

logger = logging.getLogger(__name__)


# ── Preprocessing ────────────────────────────────────────────────────────────

def preprocess_frame(frame: np.ndarray) -> np.ndarray:
    """
    Enhance image quality for better recognition in low-light conditions.

    Steps:
      1. Convert to LAB color space
      2. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) on L channel
      3. Convert back to BGR
    """
    lab   = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # CLAHE improves contrast in poor lighting
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l     = clahe.apply(l)

    enhanced = cv2.merge((l, a, b))
    result   = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    return result


# ── Liveness Detection ───────────────────────────────────────────────────────

def detect_liveness(face_region: np.ndarray) -> dict:
    """
    Basic anti-spoofing using Local Binary Pattern (LBP) texture analysis.

    Real human faces have higher texture variance than printed photos
    or screens. This is not 100% foolproof but covers basic spoofing.

    Args:
        face_region: Cropped face image (BGR)

    Returns:
        dict with 'is_live' (bool) and 'score' (float)
    """
    try:
        gray    = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (64, 64))

        # Compute LBP manually using local variance
        # Higher variance in texture = more likely a real face
        lbp_var = compute_lbp_variance(resized)

        is_live = lbp_var > LIVENESS_THRESHOLD
        return {
            "is_live": is_live,
            "score":   round(lbp_var, 2),
        }
    except Exception as e:
        logger.warning("Liveness check failed: %s", e)
        return {"is_live": True, "score": 0.0}   # Fail open if error


def compute_lbp_variance(gray_img: np.ndarray) -> float:
    """Compute variance of Local Binary Pattern histogram as texture measure.

    Uses vectorized NumPy operations instead of pixel-by-pixel Python loops
    for ~100x speedup.
    """
    # Extract the center pixels and all 8 neighbors as array slices
    center = gray_img[1:-1, 1:-1].astype(np.int16)

    # 8 neighbors: TL, T, TR, R, BR, B, BL, L  (same order as original)
    neighbors = [
        gray_img[:-2,  :-2],   # top-left
        gray_img[:-2, 1:-1],   # top
        gray_img[:-2, 2:  ],   # top-right
        gray_img[1:-1, 2:  ],  # right
        gray_img[2:,   2:  ],  # bottom-right
        gray_img[2:,  1:-1],   # bottom
        gray_img[2:,   :-2],   # bottom-left
        gray_img[1:-1,  :-2],  # left
    ]

    # Build LBP code for all pixels at once using bitwise ops
    lbp = np.zeros_like(center, dtype=np.uint8)
    for k, nb in enumerate(neighbors):
        lbp |= ((nb.astype(np.int16) >= center).astype(np.uint8) << k)

    # Compute histogram variance as texture score
    hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
    return float(np.var(hist))


# ── Face Encoding ────────────────────────────────────────────────────────────

def encode_face_from_file(image_path: str) -> Optional[np.ndarray]:
    """
    Generate a 128-d face encoding from an image file.

    Args:
        image_path: Absolute path to an image (jpg/png)

    Returns:
        NumPy array of 128 floats, or None if no face found
    """
    try:
        image      = face_recognition.load_image_file(image_path)
        locations  = face_recognition.face_locations(image, model="hog")

        if not locations:
            logger.warning("No face found in image: %s", image_path)
            return None

        encodings = face_recognition.face_encodings(
            image, known_face_locations=locations, num_jitters=NUM_JITTERS
        )
        return encodings[0] if encodings else None

    except Exception as e:
        logger.error("Error encoding face from file: %s", e)
        return None


def encode_face_from_array(rgb_image: np.ndarray) -> Optional[np.ndarray]:
    """
    Generate a 128-d face encoding from a NumPy RGB image array.

    Args:
        rgb_image: RGB (not BGR) NumPy image array

    Returns:
        NumPy array of 128 floats, or None if no face found
    """
    try:
        locations = face_recognition.face_locations(rgb_image, model="hog")

        if not locations:
            return None

        encodings = face_recognition.face_encodings(
            rgb_image, known_face_locations=locations, num_jitters=NUM_JITTERS
        )
        return encodings[0] if encodings else None

    except Exception as e:
        logger.error("Error encoding face from array: %s", e)
        return None


def encode_face_from_base64(b64_string: str) -> Optional[np.ndarray]:
    """
    Decode a base64 image string and extract face encoding.

    Args:
        b64_string: Base64-encoded image (with or without data URI prefix)

    Returns:
        NumPy face encoding or None
    """
    try:
        # Strip data URI prefix if present
        if "," in b64_string:
            b64_string = b64_string.split(",")[1]

        img_bytes  = base64.b64decode(b64_string)
        pil_image  = Image.open(BytesIO(img_bytes)).convert("RGB")
        rgb_image  = np.array(pil_image)
        return encode_face_from_array(rgb_image)

    except Exception as e:
        logger.error("Error decoding base64 image: %s", e)
        return None


# ── Recognition ──────────────────────────────────────────────────────────────

def recognize_faces_in_frame(
    frame: np.ndarray,
    known_encodings: list,
    known_names: list,
    known_ids: list,
) -> list:
    """
    Detect and identify all faces in a video frame.

    Args:
        frame:           BGR frame from webcam
        known_encodings: List of registered face encodings (NumPy arrays)
        known_names:     Corresponding names
        known_ids:       Corresponding user IDs

    Returns:
        List of dicts per detected face:
          {top, right, bottom, left, name, user_id, confidence, is_live}
    """
    # Enhance image for better detection in low light
    enhanced = preprocess_frame(frame)

    # Resize to 1/4 for faster processing, then scale locations back
    small_frame = cv2.resize(enhanced, (0, 0), fx=0.25, fy=0.25)
    rgb_small   = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    # Locate all faces in the reduced frame
    face_locations = face_recognition.face_locations(rgb_small, model="hog")

    if not face_locations:
        return []

    # Compute encodings for all detected faces
    face_encodings = face_recognition.face_encodings(
        rgb_small, known_face_locations=face_locations
    )

    results = []

    for (top, right, bottom, left), face_enc in zip(face_locations, face_encodings):
        # Scale back up to original frame size
        top    *= 4
        right  *= 4
        bottom *= 4
        left   *= 4

        name       = "Unknown"
        user_id    = None
        confidence = 0.0

        if known_encodings:
            # Compare face against all known encodings
            distances = face_recognition.face_distance(known_encodings, face_enc)
            best_idx  = int(np.argmin(distances))
            best_dist = float(distances[best_idx])

            # Convert distance to confidence score (lower distance = higher confidence)
            confidence = max(0.0, 1.0 - best_dist)

            if best_dist <= FACE_TOLERANCE and confidence >= MIN_CONFIDENCE:
                name    = known_names[best_idx]
                user_id = known_ids[best_idx]

        # Extract face region for liveness check
        face_region = frame[max(0, top):bottom, max(0, left):right]
        liveness    = detect_liveness(face_region) if face_region.size > 0 else {"is_live": True, "score": 0}

        results.append({
            "top":        top,
            "right":      right,
            "bottom":     bottom,
            "left":       left,
            "name":       name,
            "user_id":    user_id,
            "confidence": round(confidence, 3),
            "is_live":    liveness["is_live"],
            "live_score": liveness["score"],
        })

    return results


# ── Annotated Frame ──────────────────────────────────────────────────────────

def draw_face_boxes(frame: np.ndarray, recognition_results: list) -> np.ndarray:
    """
    Draw colored bounding boxes and labels on detected faces.

    Green box = recognized live face
    Orange box = recognized but possible spoof
    Red box    = unknown face
    """
    annotated = frame.copy()
    h_frame, w_frame = annotated.shape[:2]

    for r in recognition_results:
        top, right, bottom, left = r["top"], r["right"], r["bottom"], r["left"]
        name       = r["name"]
        confidence = r["confidence"]
        is_live    = r["is_live"]
        known      = name != "Unknown"

        # Choose box color (BGR)
        if not known:
            color = (0, 0, 220)        # Red for unknown
        elif not is_live:
            color = (0, 140, 255)      # Orange for spoof warning
        else:
            color = (0, 210, 90)       # Green for verified

        # Draw thick bounding rectangle
        cv2.rectangle(annotated, (left, top), (right, bottom), color, 3)

        # Build label text
        if known:
            label = f"{name} ({confidence:.0%})"
        else:
            label = "Unknown"
        if known and not is_live:
            label += " [SPOOF?]"

        # Measure text size for the background bar
        font       = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.7
        thickness  = 1
        (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

        # Place label ABOVE the box (fall back to below if too close to top edge)
        label_h  = th + baseline + 14
        label_y  = top - label_h
        if label_y < 0:
            label_y = bottom  # Fall back below box

        # Draw filled background bar for text
        bar_left  = max(left, 0)
        bar_right = min(left + tw + 16, w_frame)
        cv2.rectangle(annotated, (bar_left, label_y), (bar_right, label_y + label_h), color, cv2.FILLED)

        # Draw text on the bar
        cv2.putText(
            annotated, label,
            (bar_left + 8, label_y + th + 6),
            font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA
        )

    return annotated


# ── Base64 Frame Utilities ───────────────────────────────────────────────────

def frame_to_base64(frame: np.ndarray) -> str:
    """Convert a BGR frame to a base64-encoded JPEG string."""
    _, buffer  = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_str    = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/jpeg;base64,{b64_str}"


def base64_to_frame(b64_string: str) -> Optional[np.ndarray]:
    """Decode a base64 image string to a BGR NumPy array."""
    try:
        if "," in b64_string:
            b64_string = b64_string.split(",")[1]
        img_bytes = base64.b64decode(b64_string)
        pil_img   = Image.open(BytesIO(img_bytes)).convert("RGB")
        rgb_arr   = np.array(pil_img)
        bgr_arr   = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
        return bgr_arr
    except Exception as e:
        logger.error("base64_to_frame error: %s", e)
        return None

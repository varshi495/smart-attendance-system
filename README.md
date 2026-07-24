# 🎓 Smart Attendance System with Facial Recognition

A locally-running, AI-powered attendance system that uses your webcam to automatically recognize faces and mark attendance. Built with Python, Flask, OpenCV, and `face_recognition`.

---

## 📸 Features

| Feature | Details |
|---|---|
| Face Registration | Register users via webcam capture or image upload |
| Live Recognition | Real-time webcam facial recognition with bounding boxes |
| Duplicate Prevention | Each person can only be marked once per day |
| Anti-Spoofing | LBP texture analysis to detect photo vs. real face |
| Low-Light Enhancement | CLAHE preprocessing for poor lighting conditions |
| Multi-Face Support | Detects and identifies multiple faces simultaneously |
| Reports | Filterable attendance log with date/name filters |
| Export | Download as CSV or Excel (.xlsx) |
| Modern UI | Dark-mode web interface with glassmorphism design |

---

## 🖥️ System Requirements

- Python **3.9 or higher**
- Windows 10/11 (or Linux/macOS)
- Webcam
- **CMake** + **Visual C++ Build Tools** (for `dlib` on Windows — see below)

---

## ⚙️ Installation

### Step 1 — Install CMake (Windows only)

`face_recognition` requires `dlib`, which needs CMake.

1. Download CMake from https://cmake.org/download/
2. Run the installer — check **"Add CMake to the system PATH"**
3. Restart your terminal after installation

### Step 2 — Install Visual C++ Build Tools (Windows only)

1. Go to https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Download and run the installer
3. Select **"Desktop development with C++"** workload and install

### Step 3 — Create a Python Virtual Environment (Recommended)

```bash
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (Windows CMD)
venv\Scripts\activate.bat

# Activate (Linux/macOS)
source venv/bin/activate
```

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ **If `dlib` fails to install**, use a pre-compiled wheel instead:
> 1. Go to https://github.com/z-mahmud22/Dlib_Windows_Python3.x
> 2. Download the `.whl` file matching your Python version (e.g., `dlib-19.24.2-cp311-cp311-win_amd64.whl`)
> 3. Install it:
>    ```bash
>    pip install dlib-19.24.2-cp311-cp311-win_amd64.whl
>    pip install face_recognition
>    ```

---

## 🚀 Running the Application

### Option A — Run normally (empty database)

```bash
python app.py
```

Then open: **http://localhost:5000**

### Option B — Run with sample data (for testing/demo)

```bash
# First generate dummy data
python generate_dummy_data.py

# Then start the app
python app.py
```

> 📌 Dummy users appear in Reports and Dashboard but won't be recognized by the camera (they have no face encodings). Register real users via the web UI for full functionality.

---

## 📖 How to Use

### 1️⃣ Register a User

1. Click **"Register User"** in the sidebar
2. Enter the person's **Name**, **ID**, and optional **Department**
3. Either:
   - Click **"Start Camera"** → position face in the oval guide → click **"Capture Photo"**
   - OR click **"Upload File"** and choose an image
4. Click **"Register User"**

✅ The system will extract the face encoding and save it to the database.

### 2️⃣ Mark Attendance

1. Click **"Start Attendance"** in the sidebar
2. Click the **▶ Start** button to open the webcam
3. Registered users who look at the camera are automatically marked **Present**
4. Each person is marked only **once per day** (duplicates are ignored)
5. An orange warning appears if a spoofing attempt is detected
6. Click **⏹ Stop** when done

### 3️⃣ View & Export Reports

1. Click **"Attendance Report"** in the sidebar
2. Filter by **Date** and/or **Name**
3. Click **"Export CSV"** or **"Export Excel"** to download

---

## 📁 Project Structure

```
smart-attendance-system/
├── app.py                  ← Flask web server & all routes
├── face_engine.py          ← Face detection, recognition, anti-spoofing
├── database.py             ← SQLite operations (users + attendance)
├── attendance.py           ← Attendance marking + CSV/Excel export
├── config.py               ← App-wide configuration constants
├── requirements.txt        ← Python dependencies
├── generate_dummy_data.py  ← Script to create test data
│
├── data/
│   ├── attendance.db       ← SQLite database (auto-created)
│   ├── attendance.csv      ← Exported CSV (generated on demand)
│   └── attendance.xlsx     ← Exported Excel (generated on demand)
│
├── known_faces/            ← Saved face photos for registered users
│
├── static/
│   ├── css/style.css       ← Dark-mode UI stylesheet
│   └── js/app.js           ← Frontend JavaScript
│
└── templates/
    ├── base.html           ← Layout template (sidebar, topbar)
    ├── index.html          ← Dashboard page
    ← register.html        ← User registration page
    ├── attendance.html     ← Live webcam attendance page
    └── report.html         ← Attendance log & export page
```

---

## ⚙️ Configuration

Edit [`config.py`](config.py) to adjust settings:

| Setting | Default | Description |
|---|---|---|
| `FACE_TOLERANCE` | `0.5` | Stricter matching (lower = stricter, try 0.4–0.6) |
| `MIN_CONFIDENCE` | `0.55` | Minimum confidence to accept a match |
| `NUM_JITTERS` | `1` | Higher = more accurate, slower encoding |
| `RECHECK_DELAY` | `30` | Seconds before re-checking same person |
| `LIVENESS_THRESHOLD` | `50.0` | Anti-spoofing sensitivity |
| `PORT` | `5000` | Flask server port |

---

## 🔧 Troubleshooting

| Problem | Solution |
|---|---|
| `dlib` fails to install | Use pre-compiled wheel (see Step 4 above) |
| Camera not found | Ensure webcam is connected and not used by another app |
| Face not detected | Ensure good lighting, face the camera directly |
| Low recognition accuracy | Lower `FACE_TOLERANCE` in config.py; re-register with better photo |
| Port 5000 in use | Change `PORT` in config.py |
| Flask import error | Activate your virtual environment |

---

## 📊 CSV Export Format

The exported CSV/Excel file contains these columns:

| Column | Example |
|---|---|
| ID | 1 |
| User ID | CS001 |
| Name | Arjun Sharma |
| Date | 2024-06-04 |
| Time | 09:14:23 |
| Status | Present |
| Marked At | 2024-06-04 09:14:23 |

---

## 🚀 Bonus — Suggested Improvements

### Cloud Deployment
- Replace SQLite with **PostgreSQL** (use `psycopg2`)
- Deploy Flask on **Railway.app** or **Render.com** (free tier)
- Use **AWS S3** or **Cloudinary** to store face images

### Higher Accuracy
- Switch from `face_recognition` to **DeepFace** or **InsightFace**
- Use a GPU for faster processing with CUDA-enabled OpenCV

### Mobile Integration
- Wrap the Flask app in a **React Native WebView**
- Build a **Flutter** frontend that calls the Flask API
- Use the phone's camera via the browser (`getUserMedia` already works on mobile)

### Advanced Anti-Spoofing
- Add **eye blink detection** using facial landmarks
- Use **3D depth sensors** (Intel RealSense) for liveness
- Train a binary CNN classifier on real vs. spoof datasets

### Notifications
- Send **email/SMS** when attendance is marked (use `smtplib` or Twilio)
- Add **Telegram bot** integration for instant notifications

---

## 📄 License

MIT License — Free to use and modify for educational purposes.

---

*Built with ❤️ using Python, Flask, OpenCV, and face_recognition*

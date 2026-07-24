"""Quick syntax checker - updated to include notifications.py"""
import ast

files = [
    "app.py", "face_engine.py", "database.py",
    "attendance.py", "config.py",
    "generate_dummy_data.py", "notifications.py"
]

all_ok = True
for f in files:
    try:
        with open(f, "r", encoding="utf-8") as fh:
            source = fh.read()
        ast.parse(source)
        print(f"  OK: {f}")
    except SyntaxError as e:
        print(f"  SYNTAX ERROR in {f}: {e}")
        all_ok = False
    except FileNotFoundError:
        print(f"  NOT FOUND: {f}")

print()
if all_ok:
    print("All Python files have valid syntax!")
else:
    print("Fix the syntax errors above.")

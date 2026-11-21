"""Turns Tailor into one executable file.

    pip install -r requirements-build.txt
    python build_exe.py

Windows gives dist/Tailor.exe, Mac and Linux give dist/Tailor. A Windows .exe
has to be built on Windows. Put a .env file next to the executable to turn on
AI rewriting.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    os.chdir(HERE)
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("PyInstaller is not installed. Run:  pip install -r requirements-build.txt")
    sep = os.pathsep
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", "Tailor",
           "--add-data", f"templates{sep}templates", "--add-data", f"samples{sep}samples",
           "--collect-data", "docx",               # the Word template python-docx needs
           "--exclude-module", "pkg_resources",    # not needed, and breaks some builds
           "app.py"]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    exe = HERE / "dist" / ("Tailor.exe" if os.name == "nt" else "Tailor")
    if (HERE / ".env").exists():
        shutil.copy(HERE / ".env", exe.parent / ".env")
    print(f"\nDone. Your app is {exe}\nDouble click it and your browser will open.")


if __name__ == "__main__":
    main()

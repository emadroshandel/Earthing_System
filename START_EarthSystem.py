#!/usr/bin/env python3
# Earthing System — earthing system design to IEEE 80, IEC 60364, IEC 62305 and IEEE 142.
# Copyright (C) 2026 Emad Roshandel
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.

"""
Earthing System — double-click starter.

Use this if the .bat launchers do not run on your system (some security
software blocks batch files).  Double-click this file, or from a command
prompt in this folder run:

    python START_EarthSystem.py
    python START_EarthSystem.py --desktop
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)


def ensure(pkg, importname=None):
    try:
        __import__(importname or pkg)
        return True
    except ImportError:
        print(f"Installing {pkg} ...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            return True
        except Exception as exc:
            print(f"  could not install {pkg}: {exc}")
            return False


def main():
    print("=" * 60)
    print("  Earthing System - earthing (grounding) system design")
    print("  Python:", sys.version.split()[0], "-", sys.executable)
    print("=" * 60)
    if sys.version_info < (3, 8):
        print("\n  Python 3.8 or newer is required.")
        input("\n  Press Enter to close...")
        return 1
    ensure("numpy")
    desktop = "--desktop" in sys.argv
    try:
        if desktop:
            ensure("pywebview", "webview")
            import desktop as app
            app.main()
        else:
            import server
            server.serve()
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback
        traceback.print_exc()
        input("\n  Something went wrong. Press Enter to close...")
        return 1
    input("\n  Stopped. Press Enter to close...")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
PyInstaller Entrypoint Launcher for LNG PORV Sizing Streamlit Application
Launches Streamlit web server programmatically when executing the standalone EXE file.
"""

import sys
import os
import io
import threading
import time
import webbrowser
from streamlit.web import bootstrap

# Explicit imports to force PyInstaller static analysis inclusion
import app
import lng_thermo
import vle_thermo
import psv_sizing
import psv_database
import report_generator
import unit_converter

class DummyStream(io.TextIOBase):
    """Robust fallback stream for PyInstaller windowed mode where stdout/stderr are None."""
    def write(self, s):
        return len(s) if s else 0
    def flush(self):
        pass
    def isatty(self):
        return False
    def fileno(self):
        return -1
    @property
    def encoding(self):
        return "utf-8"

def resolve_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

def open_browser():
    """ Automatically launch web browser after 1.5 seconds """
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8501")

if __name__ == "__main__":
    # Prevent AttributeError / UnsupportedOperation on stdout/stderr in windowed mode
    if sys.stdout is None or not hasattr(sys.stdout, 'write'):
        sys.stdout = DummyStream()
    if sys.stderr is None or not hasattr(sys.stderr, 'write'):
        sys.stderr = DummyStream()

    app_path = resolve_path("app.py")
    
    # Set environment variables for headless Streamlit execution inside EXE
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    
    # Launch browser auto-opener thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    flag_options = {
        "global.developmentMode": False,
        "server.headless": True,
        "server.address": "127.0.0.1",
        "server.port": 8501,
        "browser.gatherUsageStats": False
    }
    
    # Run Streamlit web server directly via bootstrap
    bootstrap.run(app_path, is_hello=False, args=[], flag_options=flag_options)


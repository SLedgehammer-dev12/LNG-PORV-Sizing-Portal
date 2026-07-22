"""
PyInstaller Entrypoint Launcher for LNG PORV Sizing Streamlit Application
Launches Streamlit web server programmatically when executing the standalone EXE file.
"""

import sys
import os
import io
import streamlit.web.cli as stcli

# Explicit imports to force PyInstaller static analysis inclusion
import app
import lng_thermo
import psv_sizing
import psv_database
import report_generator
import unit_converter

class NullWriter(io.TextIOBase):
    """Fallback dummy writer for --windowed mode where stdout/stderr are None."""
    def write(self, s):
        return len(s)
    def flush(self):
        pass

def resolve_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

if __name__ == "__main__":
    # Prevent AttributeError on stdout/stderr when running in windowed mode
    if sys.stdout is None:
        sys.stdout = NullWriter()
    if sys.stderr is None:
        sys.stderr = NullWriter()

    app_path = resolve_path("app.py")
    
    # Set environment variables for headless Streamlit execution inside EXE
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ]
    
    sys.exit(stcli.main())


"""
PyInstaller Entrypoint Launcher for LNG PORV Sizing Streamlit Application
Launches Streamlit web server programmatically when executing the standalone EXE file.
"""

import sys
import os
import streamlit.web.cli as stcli

def resolve_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

if __name__ == "__main__":
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

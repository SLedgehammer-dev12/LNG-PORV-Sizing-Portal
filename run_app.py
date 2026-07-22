"""
PyInstaller Entrypoint Launcher for LNG PORV Sizing Streamlit Application
Launches Streamlit web server programmatically when executing the standalone EXE file.
Includes Tkinter startup dialog to let user choose target browser address (127.0.0.1 vs localhost).
"""

import sys
import os
import io
import errno
import logging
import threading
import time
import webbrowser
from streamlit import config
from streamlit.web import bootstrap

# Explicit imports to force PyInstaller static analysis inclusion
import app
import lng_thermo
import vle_thermo
import psv_sizing
import psv_database
import report_generator
import unit_converter

logger = logging.getLogger(__name__)

class DummyStream(io.TextIOBase):
    """Robust fallback stream for PyInstaller windowed mode where stdout/stderr are None."""
    def write(self, s):
        return len(s) if s else 0
    def flush(self):
        pass
    def isatty(self):
        return False
    def fileno(self):
        raise OSError(errno.EBADF, 'Bad file descriptor')
    @property
    def encoding(self):
        return "utf-8"

def resolve_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

def ask_user_launch_url() -> str:
    """
    Displays a Windows Tkinter dialog asking the user which URL address to open in the browser.
    Returns: 'http://127.0.0.1:8501', 'http://localhost:8501', or None (do not open browser).
    """
    selected_url = ["http://127.0.0.1:8501"]
    
    try:
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        root.title("LNG PORV Sizing Portalı - Tarayıcı Seçimi")
        root.geometry("480x250")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        
        # Center window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"+{x}+{y}")
        
        # Apply clean theme
        style = ttk.Style()
        try:
            style.theme_use('vista')
        except Exception:
            try:
                style.theme_use('clam')
            except Exception:
                pass
        
        lbl_title = ttk.Label(root, text="⚓ LNG PORV Sizing Portalı v1.0.0", font=("Segoe UI", 12, "bold"))
        lbl_title.pack(pady=(15, 5))
        
        lbl_msg = ttk.Label(root, text="Uygulama varsayılan web tarayıcınızda hangi adreste açılsın?", font=("Segoe UI", 9))
        lbl_msg.pack(pady=(0, 15))
        
        def choose(url):
            selected_url[0] = url
            root.destroy()
            
        btn_127 = ttk.Button(root, text="1️⃣  http://127.0.0.1:8501  (Tavsiye Edilen - Loopback IP)", command=lambda: choose("http://127.0.0.1:8501"))
        btn_127.pack(fill="x", padx=30, pady=4)
        
        btn_local = ttk.Button(root, text="2️⃣  http://localhost:8501  (Localhost Domain)", command=lambda: choose("http://localhost:8501"))
        btn_local.pack(fill="x", padx=30, pady=4)
        
        btn_none = ttk.Button(root, text="3️⃣  Tarayıcıyı Otomatik Açma (Sadece Sunucuyu Başlat)", command=lambda: choose(None))
        btn_none.pack(fill="x", padx=30, pady=4)
        
        root.protocol("WM_DELETE_WINDOW", lambda: choose("http://127.0.0.1:8501"))
        root.mainloop()
    except Exception as e:
        logger.warning(f"Could not display Tkinter popup, defaulting to 127.0.0.1: {e}")
        
    return selected_url[0]

def open_browser_url(url: str):
    """ Automatically launch chosen web browser URL after 1.5 seconds """
    if not url:
        return
    time.sleep(1.5)
    webbrowser.open(url)

if __name__ == "__main__":
    # Prevent AttributeError / UnsupportedOperation on stdout/stderr in windowed mode
    if sys.stdout is None or not hasattr(sys.stdout, 'write'):
        sys.stdout = DummyStream()
    if sys.stderr is None or not hasattr(sys.stderr, 'write'):
        sys.stderr = DummyStream()

    # Verify PyInstaller frozen static directory
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        meipass_st_static = os.path.join(sys._MEIPASS, "streamlit", "static")
        if not os.path.exists(meipass_st_static):
            meipass_st_static = os.path.join(sys._MEIPASS, "static")
            
        if os.path.exists(meipass_st_static):
            try:
                import streamlit.file_util as fu
                fu.get_static_dir = lambda: meipass_st_static
            except Exception:
                pass

    app_path = resolve_path("app.py")
    
    # Set environment variables for headless Streamlit execution inside EXE
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    
    # Explicitly set Streamlit config options before launch to prevent developmentMode / localhost:3000 redirects
    try:
        config.set_option("global.developmentMode", False)
        config.set_option("server.headless", True)
        config.set_option("server.address", "127.0.0.1")
        config.set_option("server.port", 8501)
        config.set_option("server.enableStaticServing", True)
        config.set_option("browser.gatherUsageStats", False)
        config.set_option("browser.serverAddress", "127.0.0.1")
        config.set_option("browser.serverPort", 8501)
    except Exception as e:
        logger.warning(f"Could not set Streamlit config options: {e}")

    # Monkeypatch CLI output functions to prevent OSError [Errno 9] Bad file descriptor in PyInstaller windowed mode
    try:
        import click
        click.echo = lambda *args, **kwargs: None
        click.secho = lambda *args, **kwargs: None
    except Exception:
        pass

    try:
        import streamlit.cli_util
        streamlit.cli_util.print_to_cli = lambda *args, **kwargs: None
    except Exception:
        pass

    try:
        import streamlit.web.bootstrap
        streamlit.web.bootstrap._print_url = lambda *args, **kwargs: None
    except Exception:
        pass

    # Prompt user for launch URL choice (127.0.0.1 vs localhost vs None)
    chosen_url = ask_user_launch_url()
    
    if chosen_url:
        threading.Thread(target=open_browser_url, args=(chosen_url,), daemon=True).start()
    
    flag_options = {
        "global.developmentMode": False,
        "server.headless": True,
        "server.address": "127.0.0.1",
        "server.port": 8501,
        "browser.gatherUsageStats": False
    }
    
    # Run Streamlit web server directly via bootstrap
    bootstrap.run(app_path, is_hello=False, args=[], flag_options=flag_options)

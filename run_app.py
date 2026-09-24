"""
PyInstaller Entrypoint Launcher for LNG PORV Sizing Streamlit Application
Launches Streamlit web server programmatically when executing the standalone EXE file.
Includes Tkinter startup dialog to let user choose target browser address (127.0.0.1 vs localhost).
"""

import errno
import io
import logging
import os
import socket
import sys
import threading
import time
import webbrowser

from streamlit import config
from streamlit.web import bootstrap

# Explicit imports to force PyInstaller static analysis inclusion.
# CRITICAL: these imports are intentionally "unused" in code — they exist only so
# PyInstaller bundles the local modules that Streamlit's script (app.py) imports at
# runtime from the extracted _MEIPASS directory. DO NOT REMOVE THEM (see ruff.toml
# per-file-ignores and test_module_imports_for_executability).
import app  # noqa: F401
import lng_thermo  # noqa: F401
import vle_thermo  # noqa: F401
import psv_sizing  # noqa: F401
import psv_database  # noqa: F401
import report_generator  # noqa: F401
import unit_converter  # noqa: F401
from version_checker import CURRENT_VERSION

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8501


def find_free_port(preferred_port: int = DEFAULT_PORT, max_tries: int = 10) -> int:
    """Returns the first free localhost TCP port starting from preferred_port."""
    for port in range(preferred_port, preferred_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    logger.warning(f"Could not find a free port in range {preferred_port}-{preferred_port + max_tries}; using {preferred_port}.")
    return preferred_port

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

def ask_user_launch_url(port: int = DEFAULT_PORT) -> str:
    """
    Displays a Tkinter dialog asking the user which URL address to open in the browser.
    Returns: 'http://127.0.0.1:<port>', 'http://localhost:<port>', or None (do not open browser).
    """
    selected_url = [f"http://127.0.0.1:{port}"]

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

        lbl_title = ttk.Label(root, text=f"⚓ LNG PORV Sizing Portalı v{CURRENT_VERSION}", font=("Segoe UI", 12, "bold"))
        lbl_title.pack(pady=(15, 5))

        lbl_msg = ttk.Label(root, text="Uygulama varsayılan web tarayıcınızda hangi adreste açılsın?", font=("Segoe UI", 9))
        lbl_msg.pack(pady=(0, 15))

        def choose(url):
            selected_url[0] = url
            root.destroy()

        btn_127 = ttk.Button(root, text=f"1️⃣  http://127.0.0.1:{port}  (Tavsiye Edilen - Loopback IP)", command=lambda: choose(f"http://127.0.0.1:{port}"))
        btn_127.pack(fill="x", padx=30, pady=4)

        btn_local = ttk.Button(root, text=f"2️⃣  http://localhost:{port}  (Localhost Domain)", command=lambda: choose(f"http://localhost:{port}"))
        btn_local.pack(fill="x", padx=30, pady=4)

        btn_none = ttk.Button(root, text="3️⃣  Tarayıcıyı Otomatik Açma (Sadece Sunucuyu Başlat)", command=lambda: choose(None))
        btn_none.pack(fill="x", padx=30, pady=4)

        root.protocol("WM_DELETE_WINDOW", lambda: choose(f"http://127.0.0.1:{port}"))
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

    # Pick a free port (falls back to the next free port if 8501 is occupied)
    port = find_free_port(DEFAULT_PORT)
    if port != DEFAULT_PORT:
        logger.warning(f"Port {DEFAULT_PORT} is in use; switching to {port}.")

    # Explicitly set Streamlit config options before launch to prevent developmentMode / localhost:3000 redirects
    try:
        config.set_option("global.developmentMode", False)
        config.set_option("server.headless", True)
        config.set_option("server.address", "127.0.0.1")
        config.set_option("server.port", port)
        config.set_option("server.enableStaticServing", True)
        config.set_option("browser.gatherUsageStats", False)
        config.set_option("browser.serverAddress", "127.0.0.1")
        config.set_option("browser.serverPort", port)
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
    chosen_url = ask_user_launch_url(port)

    if chosen_url:
        threading.Thread(target=open_browser_url, args=(chosen_url,), daemon=True).start()

    flag_options = {
        "global.developmentMode": False,
        "server.headless": True,
        "server.address": "127.0.0.1",
        "server.port": port,
        "browser.gatherUsageStats": False
    }

    # Run Streamlit web server directly via bootstrap
    try:
        bootstrap.run(app_path, is_hello=False, args=[], flag_options=flag_options)
    except Exception as err:
        logger.exception("Streamlit sunucusu başlatılamadı")
        try:
            import tkinter as tk
            from tkinter import messagebox
            _root = tk.Tk()
            _root.withdraw()
            messagebox.showerror(
                "LNG PORV Sizing Portalı",
                f"Uygulama başlatılamadı:\n{err}\n\nLütfen port {port} kullanımda değilse tekrar deneyin."
            )
            _root.destroy()
        except Exception:
            pass
        sys.exit(1)

"""Start PageOne or show a local installation notice without third-party packages."""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path


APP_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_PORT = 5000
REQUIRED_MODULES = ("flask", "openai", "yt_dlp")
STARTUP_FILES = {
    "/": (APP_DIRECTORY / "templates" / "startup_error.html", "text/html; charset=utf-8"),
    "/static/css/pageone.css": (APP_DIRECTORY / "static" / "css" / "pageone.css", "text/css; charset=utf-8"),
}


class StartupNoticeHandler(BaseHTTPRequestHandler):
    """Serve only the static installation notice and its local visual files."""

    def do_GET(self) -> None:
        """Show the notice without opening the project directory to the browser."""
        file_entry = STARTUP_FILES.get(self.path.split("?", 1)[0])
        if not file_entry:
            self.send_error(404)
            return
        path, content_type = file_entry
        try:
            data = path.read_bytes()
        except OSError:
            self.send_error(500)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'")
        self.end_headers()
        self.wfile.write(data)


def missing_modules() -> list[str]:
    """List packages needed for the supported launch command."""
    return [module for module in REQUIRED_MODULES if importlib.util.find_spec(module) is None]


def startup_logger() -> logging.Logger:
    """Send startup failures to the terminal and rotating local log."""
    logger = logging.getLogger("pageone.startup")
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    terminal = logging.StreamHandler(sys.stderr)
    terminal.setFormatter(formatter)
    logger.addHandler(terminal)
    data_directory = Path(os.environ.get("PAGEONE_DATA_DIR", str(APP_DIRECTORY / "instance"))).expanduser()
    try:
        data_directory.mkdir(parents=True, exist_ok=True)
        log = RotatingFileHandler(data_directory / "pageone.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        log.setFormatter(formatter)
        logger.addHandler(log)
    except OSError as error:
        logger.error("Startup log file unavailable (%s)", type(error).__name__)
    return logger


def local_port() -> int:
    """Use a valid local port or the default port for the browser page."""
    try:
        port = int(os.environ.get("PAGEONE_PORT", str(DEFAULT_PORT)))
    except ValueError:
        return DEFAULT_PORT
    return port if 1 <= port <= 65535 else DEFAULT_PORT


def show_startup_notice(reason: str) -> None:
    """Log the cause and serve a script-free in-app notice on loopback."""
    logger = startup_logger()
    logger.error("PageOne startup failed: %s", reason)
    address = ("127.0.0.1", local_port())
    try:
        server = HTTPServer(address, StartupNoticeHandler)
    except OSError as error:
        logger.error("Startup notice could not bind to localhost (%s)", type(error).__name__)
        return
    print(f"PageOne notice: http://127.0.0.1:{address[1]}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    """Launch the app when installed or show the local startup notice."""
    missing = missing_modules()
    if missing:
        show_startup_notice(f"Missing packages: {', '.join(missing)}. Install requirements.txt.")
        return
    try:
        from app import app
    except Exception as error:
        show_startup_notice(f"App initialization failed ({type(error).__name__}).")
        return
    try:
        app.run(host="127.0.0.1", port=local_port(), debug=False, threaded=True)
    except (OSError, SystemExit) as error:
        startup_logger().error("App listener failed (%s)", type(error).__name__)


if __name__ == "__main__":
    main()

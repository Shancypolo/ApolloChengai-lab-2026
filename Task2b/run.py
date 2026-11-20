#!/usr/bin/env python3
"""Start Mole Mayhem and open it in your browser. Python standard library only."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent


class GameHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Every launch/reload uses the current local files, including during editing.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        if len(args) < 2 or str(args[1]) not in {"200", "304"}:
            super().log_message(format, *args)


def start_server(port):
    handler = partial(GameHandler, directory=str(ROOT))
    try:
        return ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError:
        if port == 0:
            raise
        # Avoid setup instructions when another app already uses the default port.
        return ThreadingHTTPServer(("127.0.0.1", 0), handler)


def main():
    parser = argparse.ArgumentParser(description="Launch WHACK! Mole Mayhem in your browser.")
    parser.add_argument("--port", type=int, default=4175, help="Preferred port (default: 4175).")
    parser.add_argument("--no-browser", action="store_true", help="Serve without opening a browser tab.")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535.")
    server = start_server(args.port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"\n  WHACK! — MOLE MAYHEM\n  {url}\n\n  Your game is ready. Press Ctrl+C here to stop.\n", flush=True)
    if not args.no_browser:
        # The socket is already listening; serve_forever can start before the browser requests it.
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Game server stopped. See you next round!", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

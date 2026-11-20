#!/usr/bin/env python3
"""Start WHACK! locally and open it in the default browser."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import webbrowser


GAME_DIR = Path(__file__).resolve().parent


def main() -> None:
    index_file = GAME_DIR / "index.html"
    if not index_file.is_file():
        raise SystemExit(f"Game entry point not found: {index_file}")

    handler = partial(SimpleHTTPRequestHandler, directory=str(GAME_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print("WHACK! is running locally.")
    print(f"Game: {url}")
    print("Keep this window open while playing. Press Ctrl+C to stop the game server.")
    try:
        browser_opened = webbrowser.open_new_tab(url)
    except webbrowser.Error:
        browser_opened = False
    if not browser_opened:
        print("Open the Game URL above in a browser if it did not open automatically.")

    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping WHACK!…")
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        print("Game server stopped.")


if __name__ == "__main__":
    main()

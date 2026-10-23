"""Check the no-dependency startup notice with only Python standard library."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


APP_DIRECTORY = Path(__file__).resolve().parents[1]


def free_local_port() -> int:
    """Reserve and release one loopback port for the smoke process."""
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def main() -> None:
    """Check the missing-package notice and the normal local launch."""
    with tempfile.TemporaryDirectory(prefix="pageone-startup-") as folder:
        port = free_local_port()
        environment = {**os.environ, "PAGEONE_PORT": str(port), "PAGEONE_DATA_DIR": folder}
        environment.pop("PYTHONPATH", None)
        process = subprocess.Popen(
            [sys.executable, "-S", "run.py"],
            cwd=APP_DIRECTORY,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            for attempt in range(40):
                try:
                    with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                        page = response.read().decode("utf-8")
                        assert response.status == 200
                        assert 'class="failure-notice"' in page
                        assert "PageOne cannot start" in page
                        assert "<script" not in page
                        break
                except OSError:
                    if attempt == 39:
                        raise
                    time.sleep(0.1)
            log_text = (Path(folder) / "pageone.log").read_text(encoding="utf-8")
            assert "Missing packages:" in log_text
        finally:
            process.terminate()
            _, terminal_text = process.communicate(timeout=5)
        assert "Missing packages:" in terminal_text

        normal_port = free_local_port()
        normal_environment = {**os.environ, "PAGEONE_PORT": str(normal_port), "PAGEONE_DATA_DIR": folder}
        normal_process = subprocess.Popen(
            [sys.executable, "run.py"], cwd=APP_DIRECTORY, env=normal_environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        try:
            for attempt in range(40):
                try:
                    with urlopen(f"http://127.0.0.1:{normal_port}/", timeout=1) as response:
                        page = response.read().decode("utf-8")
                        assert response.status == 200
                        assert 'class="hero-logo"' in page
                        assert 'class="failure-notice"' not in page
                        break
                except OSError:
                    if attempt == 39:
                        raise
                    time.sleep(0.1)
        finally:
            normal_process.terminate()
            normal_process.communicate(timeout=5)
        print("Startup smoke passed: missing-package notice, terminal, log, and normal launch.")


if __name__ == "__main__":
    main()

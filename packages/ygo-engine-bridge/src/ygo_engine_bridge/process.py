"""Subprocess management for ygopro-engine."""

from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

# Default paths relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parents[4]  # ygo/
_DEFAULT_ENGINE = _PROJECT_ROOT / "libs" / "ygopro-engine" / "build" / "ygopro-engine.exe"
_DEFAULT_CARD_DB = _PROJECT_ROOT / "libs" / "ygopro-engine" / "build" / "cards.cdb"
_DEFAULT_SCRIPTS = _PROJECT_ROOT / "libs" / "ygopro-scripts"


class EngineProcess:
    """Manages a ygopro-engine subprocess."""

    def __init__(self, engine_path: Optional[str] = None):
        """Initialize with path to ygopro-engine executable.

        Args:
            engine_path: Path to ygopro-engine binary. If None, uses default build location.
        """
        # Always prefer the default absolute path (relative to this file)
        # Environment variable may be a relative path that doesn't resolve correctly
        self._engine_path = str(_DEFAULT_ENGINE)
        self._process: Optional[subprocess.Popen] = None
        self._card_db_path = ""
        self._scripts_path = ""

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self, card_db_path: str = "", scripts_path: str = "") -> bool:
        """Start the engine subprocess.

        Args:
            card_db_path: Path to cards.cdb file
            scripts_path: Path to Lua scripts directory

        Returns:
            True if started successfully
        """
        if self.is_running:
            return True

        self._card_db_path = card_db_path
        self._scripts_path = scripts_path

        cmd = [self._engine_path]
        if card_db_path:
            cmd.append(card_db_path)
        if scripts_path:
            cmd.append(scripts_path)

        try:
            # Use DEVNULL for stderr to avoid blocking on pipe buffer
            # Error messages will be captured via polling when needed
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,  # Line-buffered
            )
            return True
        except FileNotFoundError:
            raise RuntimeError(
                f"ygopro-engine not found at: {self._engine_path}. "
                "Build it first: cd libs/ygopro-engine && cmake -B build && cmake --build build"
            )

    def stop(self):
        """Stop the engine subprocess."""
        if self._process:
            self._process.stdin.close()
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    def send_command(self, cmd: dict, timeout: float = 30.0) -> dict:
        """Send a JSON command and receive a JSON response.

        Args:
            cmd: Command dictionary to send
            timeout: Maximum time to wait for response in seconds

        Returns:
            Response dictionary from engine

        Raises:
            RuntimeError: If engine is not running or returns an error
        """
        import threading

        if not self.is_running:
            raise RuntimeError("Engine is not running. Call start() first.")

        # Send command
        cmd_json = json.dumps(cmd) + "\n"
        self._process.stdin.write(cmd_json)
        self._process.stdin.flush()

        # Read response with timeout using a background thread
        result = [None]
        error = [None]

        def read_line():
            try:
                result[0] = self._process.stdout.readline()
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=read_line, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # Timeout - kill the engine process
            self.stop()
            raise RuntimeError(f"Engine response timeout after {timeout}s. Engine process killed.")

        if error[0]:
            raise RuntimeError(f"Error reading from engine: {error[0]}")

        response_line = result[0]
        if not response_line:
            raise RuntimeError(f"Engine closed unexpectedly. Exit code: {self._process.returncode}")

        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON from engine: {e}")

        return response

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

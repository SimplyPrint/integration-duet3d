"""Watchdog timer implementation for the Meltingplot Duet SimplyPrint.io Connector."""

import _thread
import asyncio
import threading
import time


class Watchdog:
    """A simple watchdog timer that raises KeyboardInterrupt if the timer expires."""

    def __init__(self, timeout: float):
        """Initialize the watchdog with a timeout in seconds."""
        self.timeout = timeout
        self._last_reset = time.monotonic()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._watchdog_thread, daemon=True)

    def start(self):
        """Start the watchdog thread."""
        self._thread.start()

    def stop(self):
        """Stop the watchdog thread."""
        self._stop_event.set()
        self._thread.join()

    async def reset(self):
        """Reset the watchdog timer asynchronously."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._reset_sync)

    def _reset_sync(self):
        """Reset the watchdog timer synchronously."""
        with self._lock:
            self._last_reset = time.monotonic()

    def _watchdog_thread(self):
        """Thread that checks the watchdog timer."""
        while not self._stop_event.is_set():
            with self._lock:
                elapsed = time.monotonic() - self._last_reset
            if elapsed > self.timeout:
                # Raise KeyboardInterrupt in main thread
                _thread.interrupt_main()
                break
            time.sleep(0.1)

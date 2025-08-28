import pytest
import threading
import time
import asyncio
from meltingplot.duet_simplyprint_connector.watchdog import Watchdog

def test_watchdog_basic_reset_and_stop():
    wd = Watchdog(timeout=2)
    wd.start()
    wd.reset_sync()
    time.sleep(1)
    wd.reset_sync()
    time.sleep(1)
    wd.stop()
    assert not wd._thread.is_alive()

def test_watchdog_triggers_interrupt(monkeypatch):
    triggered = []

    def fake_interrupt_main():
        triggered.append(True)

    monkeypatch.setattr("meltingplot.duet_simplyprint_connector.watchdog._thread.interrupt_main", fake_interrupt_main)
    wd = Watchdog(timeout=0.5)
    wd.start()
    time.sleep(2)
    wd.stop()
    assert triggered

def test_watchdog_async_reset():
    wd = Watchdog(timeout=2)
    wd.start()
    async def do_reset():
        await wd.reset()
    asyncio.run(do_reset())
    wd.stop()
    assert not wd._thread.is_alive()

def test_watchdog_multithreaded_resets():
    wd = Watchdog(timeout=2)
    wd.start()
    threads = []
    def reset_worker():
        for _ in range(5):
            wd.reset_sync()
            time.sleep(0.1)
    for _ in range(10):
        t = threading.Thread(target=reset_worker)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    wd.stop()
    assert not wd._thread.is_alive()

def test_watchdog_multithreaded_stop():
    wd = Watchdog(timeout=2)
    wd.start()
    stop_threads = []
    def stop_worker():
        time.sleep(0.5)
        wd.stop()
    for _ in range(10):
        t = threading.Thread(target=stop_worker)
        stop_threads.append(t)
        t.start()
    for t in stop_threads:
        t.join()
    assert not wd._thread.is_alive()

def test_watchdog_async_reset_multithreaded(monkeypatch):
    # Patch interrupt_main to avoid actually raising KeyboardInterrupt
    triggered = []

    def fake_interrupt_main():
        triggered.append(True)

    monkeypatch.setattr("meltingplot.duet_simplyprint_connector.watchdog._thread.interrupt_main", fake_interrupt_main)
    wd = Watchdog(timeout=1)
    wd.start()
    wd.reset_sync(offset=5)  # Set initial offset to avoid immediate trigger

    async def reset_worker():
        await wd.reset()
        await asyncio.sleep(5)

    async def run_workers():
        tasks = [asyncio.create_task(reset_worker()) for _ in range(10)]
        await asyncio.gather(*tasks)

    asyncio.run(run_workers())
    time.sleep(5)  # Wait for watchdog to possibly trigger
    wd.stop()
    assert triggered  # Should have triggered interrupt_main

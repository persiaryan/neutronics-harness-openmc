"""Keep tmpfs alive until the host freezes it and retrieves candidate artifacts."""
import signal

while True:
    signal.pause()

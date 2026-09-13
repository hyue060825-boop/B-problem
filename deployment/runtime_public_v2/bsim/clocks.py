import time


class SystemClock:
    def monotonic(self):
        return time.monotonic()

    def timestamp_ms(self):
        return time.time_ns() // 1000000


class ManualClock:
    def __init__(self, elapsed=0, epoch_ms=1760000000000):
        self.elapsed, self.epoch_ms = elapsed, epoch_ms

    def monotonic(self):
        return self.elapsed

    def timestamp_ms(self):
        return self.epoch_ms + int(self.elapsed * 1000)

    def advance(self, seconds):
        if seconds < 0:
            raise ValueError('clock cannot run backwards')
        self.elapsed += seconds

import datetime


class Timer:

    def __init__(self):
        self._start_time = None

    def start_timing(self):
        self._start_time = datetime.datetime.now()

    def take_sample(self):
        time_now = datetime.datetime.now()
        diff = time_now - self._start_time
        return diff

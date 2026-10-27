"""Owner-scoped cancellation of SQL requests and their secured connections."""
from contextlib import contextmanager
import re
import threading
import time
import uuid


class QueryRequestError(RuntimeError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class _Request:
    def __init__(self, key):
        self.key = key
        self.cancelled = threading.Event()
        self.finished = threading.Event()
        self.lock = threading.Lock()
        self.connections = {}
        self.interrupter = None

    def check(self):
        if self.cancelled.is_set():
            raise QueryRequestError('SQL request cancelled.', 499)

    def attach(self, connection):
        with self.lock:
            self.connections[id(connection)] = connection
            if self.cancelled.is_set():
                connection.interrupt()
        self.check()

    def close_connection(self, connection):
        # DuckDB interruption may run on another thread, but closing must never
        # race that interrupt against a freed native connection.
        with self.lock:
            self.connections.pop(id(connection), None)
            connection.close()

    def interrupt(self):
        with self.lock:
            for connection in self.connections.values():
                try:
                    connection.interrupt()
                except Exception:
                    pass

    def _repeat_interrupt(self):
        # A one-shot interrupt can land just before DuckDB starts a statement
        # and be reset by that statement. Repeat only for cancelled requests.
        while not self.finished.wait(.05):
            self.interrupt()

    def cancel(self):
        with self.lock:
            if self.finished.is_set():
                return
            self.cancelled.set()
            if self.interrupter is None:
                self.interrupter = threading.Thread(target=self._repeat_interrupt, daemon=True)
                self.interrupter.start()
        self.interrupt()

    def finish(self):
        self.finished.set()
        if self.interrupter:
            self.interrupter.join(.2)


class QueryCancellation:
    def __init__(self, *, early_limit=1024, early_seconds=60):
        self.lock = threading.Lock()
        self.jobs = {}
        self.early = {}
        self.early_limit = early_limit
        self.early_seconds = early_seconds
        self.closed = False

    @staticmethod
    def request_id(value):
        if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
            raise QueryRequestError('Invalid SQL request ID.')
        return value

    def _expire(self, now):
        self.early = {key: expiry for key, expiry in self.early.items() if expiry > now}

    @contextmanager
    def request(self, owner, request_id=None):
        key = (owner, self.request_id(request_id) if request_id is not None else uuid.uuid4().hex)
        now = time.monotonic()
        job = _Request(key)
        with self.lock:
            if self.closed:
                raise QueryRequestError('The SQL service is shutting down.', 503)
            if key in self.jobs:
                raise QueryRequestError('This SQL request is already pending.', 409)
            self._expire(now)
            if self.early.pop(key, 0) > now:
                job.cancelled.set()
            self.jobs[key] = job
        try:
            job.check()
            yield job
        finally:
            with self.lock:
                self.jobs.pop(key, None)
            job.finish()

    def cancel(self, owner, request_id):
        key = (owner, self.request_id(request_id))
        now = time.monotonic()
        with self.lock:
            job = self.jobs.get(key)
            if job is None:
                self._expire(now)
                if len(self.early) >= self.early_limit:
                    self.early.pop(next(iter(self.early)))
                self.early[key] = now + self.early_seconds
        if job is not None:
            job.cancel()
        return job is not None

    def close(self):
        with self.lock:
            self.closed = True
            jobs = list(self.jobs.values())
            self.early.clear()
        for job in jobs:
            job.cancel()

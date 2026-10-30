"""Bounded, thread-safe cache with comparable FIFO, LRU and LFU policies."""
import math
import threading
import time
from dataclasses import dataclass


@dataclass
class Entry:
    value: object
    inserted: int
    touched: int
    frequency: int
    expires: float | None


class Cache:
    def __init__(self, capacity=128, policy="lru", clock=time.monotonic):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        if policy not in ("fifo", "lru", "lfu"):
            raise ValueError("policy must be fifo, lru or lfu")
        self.capacity, self.policy, self.clock = capacity, policy, clock
        self._entries = {}
        self._lock = threading.RLock()
        self._sequence = 0
        self._stats = dict(hits=0, misses=0, evictions=0, expirations=0, writes=0)

    def _tick(self):
        self._sequence += 1
        return self._sequence

    def _purge(self):
        now = self.clock()
        expired = [key for key, entry in self._entries.items() if entry.expires is not None and entry.expires <= now]
        for key in expired:
            del self._entries[key]
        self._stats["expirations"] += len(expired)
        return len(expired)

    @staticmethod
    def _ttl(ttl):
        if ttl is not None and (isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or not math.isfinite(ttl) or ttl <= 0):
            raise ValueError("ttl must be a finite positive duration or None")

    def set(self, key, value, *, ttl=None):
        hash(key)
        self._ttl(ttl)
        with self._lock:
            self._purge()
            sequence = self._tick()
            previous = self._entries.get(key)
            if previous is None and len(self._entries) >= self.capacity:
                if self.policy == "fifo":
                    victim = min(self._entries, key=lambda k: self._entries[k].inserted)
                elif self.policy == "lru":
                    victim = min(self._entries, key=lambda k: self._entries[k].touched)
                else:
                    victim = min(self._entries, key=lambda k: (self._entries[k].frequency, self._entries[k].touched))
                del self._entries[victim]
                self._stats["evictions"] += 1
            self._entries[key] = Entry(value, previous.inserted if previous else sequence,
                                       sequence, previous.frequency + 1 if previous else 1,
                                       None if ttl is None else self.clock() + ttl)
            self._stats["writes"] += 1

    def get(self, key, default=None):
        with self._lock:
            self._purge()
            entry = self._entries.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return default
            entry.touched = self._tick()
            entry.frequency += 1
            self._stats["hits"] += 1
            return entry.value

    def contains(self, key):
        """Non-touching lookup: does not alter hit counters or eviction order."""
        with self._lock:
            self._purge()
            return key in self._entries

    def delete(self, key):
        with self._lock:
            self._purge()
            if key not in self._entries:
                return False
            del self._entries[key]
            return True

    def clear(self):
        with self._lock:
            self._entries.clear()

    def purge(self):
        with self._lock:
            return self._purge()

    def stats(self):
        with self._lock:
            self._purge()
            stats = self._stats.copy()
            requests = stats["hits"] + stats["misses"]
            return stats | {"size": len(self._entries), "capacity": self.capacity,
                            "policy": self.policy, "hit_rate": stats["hits"] / requests if requests else 0.0}

    def snapshot(self):
        """Shallow value snapshot; caller mutations do not alter the key table."""
        with self._lock:
            self._purge()
            return {key: entry.value for key, entry in self._entries.items()}

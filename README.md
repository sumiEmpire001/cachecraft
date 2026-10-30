# Cachecraft

A thread-safe, bounded Python cache with **FIFO, LRU and LFU** eviction, per-entry expiry, metrics and a reproducible policy-comparison CLI. Built for Lord_Sumi's portfolio.

## Try it

Python 3.10+; no third-party runtime dependencies.

```bash
git clone https://github.com/sumiEmpire001/cachecraft.git
cd cachecraft
python -m unittest discover -s tests -v
python -m cachecraft --capacity 8 --requests 1000 --seed 7
python -m cachecraft --capacity 8 --requests 1000 --seed 7 --csv
```

The CLI generates a **synthetic** hot/cold workload and replays the exact same requests through each policy. Results report hits, misses, evictions, writes and hit rate. This compares behavior on that fixture; it is not a timing benchmark or a universal ranking of eviction algorithms.

```python
from cachecraft import Cache

cache = Cache(capacity=2, policy="lru")
cache.set("profile", {"name": "Demo"}, ttl=30)
assert cache.get("profile")["name"] == "Demo"
assert cache.contains("profile")
print(cache.stats())
cache.delete("profile")
```

## Policy contract

| Policy | Eviction choice | Existing-key update |
|---|---|---|
| FIFO | Earliest insertion | Keeps insertion order |
| LRU | Least recently touched | Counts as a touch |
| LFU | Lowest frequency, then least recently touched | Increments frequency and counts as a touch |

`get` records a hit/miss and updates frequency and recency on a hit. `contains`, `snapshot` and `stats` do not count as accesses, but purge expired entries. Values such as `None` and `False` are supported. Pass a unique sentinel as the default when you need to distinguish a stored `None` from a miss.

Expiry uses a monotonic clock by default. An entry expires exactly at its deadline. A replacement resets its TTL; omitting TTL makes the replacement non-expiring. Expired keys are removed before capacity eviction and counted separately as expirations. There is no background expiry thread.

## Architecture and verification

Each entry stores insertion sequence, access sequence, frequency and optional expiry time. One reentrant lock protects each public operation and its counters. Sequence counters break ties independently of clock resolution. This implementation prioritizes clarity: purge and eviction scan entries, so operations may take O(capacity) time.

Local validation on 30 October 2026: **12 tests passed**. Tests cover all three eviction policies, LFU ties, exact expiry boundaries, TTL replacement, non-touching inspection, falsy values, invalid configurations, seeded workload repeatability and 300 concurrent writes for each policy. GitHub Actions is configured separately for Python 3.10, 3.12 and 3.13.

## Limits

Capacity is an entry count, not a byte limit. Values are held by reference and snapshots are shallow: mutating a stored object outside the cache is not protected by the cache lock. Individual operations are atomic; a caller's `get`-compute-`set` sequence is not. There is no cross-process coordination, persistence, distributed invalidation, stampede protection or LFU ageing. Counters survive `clear`; removing entries does not reset historical metrics. The workload comparison is synthetic and does not measure real service latency.

MIT license; see [LICENSE](LICENSE).

import concurrent.futures
import unittest
from cachecraft import Cache
from cachecraft.__main__ import compare


class CacheTests(unittest.TestCase):
    def test_lru_evicts_least_recently_used(self):
        cache = Cache(2, "lru")
        cache.set("a", 1)
        cache.set("b", 2)
        self.assertEqual(cache.get("a"), 1)
        cache.set("c", 3)
        self.assertFalse(cache.contains("b"))
        self.assertTrue(cache.contains("a"))

    def test_fifo_reads_and_updates_do_not_change_insertion_order(self):
        cache = Cache(2, "fifo")
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")
        cache.set("a", 10)
        cache.set("c", 3)
        self.assertFalse(cache.contains("a"))

    def test_lfu_keeps_hot_key_and_breaks_ties_by_recency(self):
        cache = Cache(2, "lfu")
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")
        cache.set("c", 3)
        self.assertTrue(cache.contains("a"))
        self.assertFalse(cache.contains("b"))
        cache = Cache(2, "lfu")
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        self.assertFalse(cache.contains("a"))

    def test_expiry_boundary_and_metrics(self):
        now = [0.0]
        cache = Cache(2, clock=lambda: now[0])
        cache.set("a", 1, ttl=2)
        now[0] = 1.99
        self.assertEqual(cache.get("a"), 1)
        now[0] = 2
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.stats()["expirations"], 1)
        self.assertEqual(cache.stats()["evictions"], 0)

    def test_expired_entry_frees_capacity_before_eviction(self):
        now = [0]
        cache = Cache(2, clock=lambda: now[0])
        cache.set("expired", 1, ttl=1)
        cache.set("valid", 2)
        now[0] = 1
        cache.set("new", 3)
        self.assertTrue(cache.contains("valid"))
        self.assertEqual(cache.stats()["evictions"], 0)

    def test_replacement_resets_ttl_without_duplicate_entry(self):
        now = [0]
        cache = Cache(1, clock=lambda: now[0])
        cache.set("a", 1, ttl=1)
        cache.set("a", 2)
        now[0] = 10
        self.assertEqual(cache.get("a"), 2)
        self.assertEqual(cache.stats()["size"], 1)

    def test_none_and_false_are_values_not_misses(self):
        cache = Cache(2)
        marker = object()
        cache.set("none", None)
        cache.set("false", False)
        self.assertIsNone(cache.get("none", marker))
        self.assertIs(cache.get("false", marker), False)
        self.assertIs(cache.get("missing", marker), marker)
        self.assertEqual(cache.stats()["hits"], 2)

    def test_contains_does_not_change_stats_or_lru(self):
        cache = Cache(2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.contains("a")
        cache.set("c", 3)
        self.assertFalse(cache.contains("a"))
        self.assertEqual(cache.stats()["hits"], 0)

    def test_stats_snapshot_and_deletion(self):
        cache = Cache(2)
        cache.set("a", 1)
        cache.get("a")
        cache.get("missing")
        self.assertEqual(cache.stats()["hit_rate"], .5)
        snapshot = cache.snapshot()
        snapshot["b"] = 2
        self.assertFalse(cache.contains("b"))
        self.assertTrue(cache.delete("a"))
        self.assertFalse(cache.delete("a"))
        cache.clear()
        self.assertEqual(cache.stats()["size"], 0)

    def test_invalid_configuration_and_ttl(self):
        for capacity in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                Cache(capacity)
        with self.assertRaises(ValueError):
            Cache(policy="unknown")
        cache = Cache(1)
        for ttl in (0, -1, True, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                cache.set("a", 1, ttl=ttl)
        self.assertEqual(cache.stats()["size"], 0)

    def test_concurrent_access_preserves_capacity_and_write_count(self):
        for policy in ("fifo", "lru", "lfu"):
            cache = Cache(8, policy)
            def work(n):
                cache.set(n, n)
                cache.get(n)
                self.assertLessEqual(cache.stats()["size"], 8)
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                list(pool.map(work, range(300)))
            self.assertEqual(cache.stats()["writes"], 300)
            self.assertEqual(cache.stats()["size"], 8)

    def test_policy_comparison_replays_identical_seed_and_counts(self):
        one = compare(capacity=8, requests=500, seed=7)
        self.assertEqual(one, compare(capacity=8, requests=500, seed=7))
        for row in one:
            self.assertEqual(row["hits"] + row["misses"], 500)
            self.assertEqual(row["writes"], row["misses"])
            self.assertLessEqual(row["size"], 8)


if __name__ == "__main__":
    unittest.main()

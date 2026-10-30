import argparse
import csv
import io
import json
import random
from .cache import Cache


def compare(capacity=32, requests=1000, seed=7):
    if type(requests) is not int or not 1 <= requests <= 1_000_000:
        raise ValueError("requests must be 1..1000000")
    rng = random.Random(seed)
    # Synthetic hot/cold workload. Every policy sees exactly the same requests.
    workload = [rng.randrange(8) if rng.random() < .8 else rng.randrange(128) for _ in range(requests)]
    rows = []
    missing = object()
    for policy in ("fifo", "lru", "lfu"):
        cache = Cache(capacity, policy)
        for key in workload:
            if cache.get(key, missing) is missing:
                cache.set(key, key * key)
        rows.append(cache.stats() | {"requests": requests, "seed": seed})
    return rows


def main():
    parser = argparse.ArgumentParser(description="Compare cache policies on a seeded synthetic workload")
    parser.add_argument("--capacity", type=int, default=32)
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--csv", action="store_true")
    args = parser.parse_args()
    try:
        rows = compare(args.capacity, args.requests, args.seed)
        if args.csv:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
            print(output.getvalue(), end="")
        else:
            print(json.dumps(rows, indent=2))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()

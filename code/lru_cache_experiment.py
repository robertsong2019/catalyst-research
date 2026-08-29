"""LRU Cache Experiment for Catalyst Research

Experiment #1: Replace FIFO with LRU caching strategy in SidechannelCache
Hypothesis: LRU will provide better hit rates than FIFO for typical access patterns
Time budget: 30 minutes (Cycle 1)

Methodology:
1. Implement LRU version of SidechannelCache
2. Compare hit rates between FIFO and LRU on same test data
3. Measure performance impact
4. If successful, commit and record results

Metric: Cache hit rate improvement (higher is better)
"""

import hashlib
import time
from typing import Any, Callable
from collections import OrderedDict


class SidechannelCacheLRU:
    """SidechannelCache with LRU eviction policy (replaces FIFO)."""

    def __init__(self, maxsize: int = 8192):
        self._vecs: dict[str, list[float]] = {}
        self._lru_order: OrderedDict[str, None] = OrderedDict()  # LRU order
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self.embed_calls = 0

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> list[float] | None:
        """Get vector for text, updating LRU order on hit."""
        key = self._key(text)
        if key in self._vecs:
            # Mark as recently used by moving to end
            self._lru_order.move_to_end(key)
            self.hits += 1
            return self._vecs[key]
        self.misses += 1
        return None

    def put(self, text: str, vec: list[float]) -> None:
        """Put vector, using LRU eviction when at capacity."""
        key = self._key(text)
        if key not in self._vecs:
            # Mark as recently used by adding to end
            self._lru_order[key] = None
            if len(self._lru_order) > self.maxsize:
                # Evict least recently used (first item)
                oldest_key = next(iter(self._lru_order))
                self._lru_order.pop(oldest_key)
                self._vecs.pop(oldest_key, None)
        self._vecs[key] = list(vec)

    def forget(self) -> None:
        """Drop all vectors (counters kept for audit)."""
        self._vecs.clear()
        self._lru_order.clear()

    def stats(self) -> dict:
        """Return cache statistics."""
        total = self.hits + self.misses
        return {
            "size": len(self._vecs),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "embed_calls": self.embed_calls,
            "hit_rate": self.hits / total if total else 0.0
        }


class SidechannelCacheFIFO:
    """Original FIFO version for comparison."""

    def __init__(self, maxsize: int = 8192):
        self._vecs: dict[str, list[float]] = {}
        self._order: list[str] = []        # FIFO eviction order
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self.embed_calls = 0

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> list[float] | None:
        key = self._key(text)
        if key in self._vecs:
            self.hits += 1
            return self._vecs[key]
        self.misses += 1
        return None

    def put(self, text: str, vec: list[float]) -> None:
        key = self._key(text)
        if key not in self._vecs:
            self._order.append(key)
            if len(self._order) > self.maxsize:
                self._vecs.pop(self._order.pop(0), None)
        self._vecs[key] = list(vec)

    def forget(self) -> None:
        self._vecs.clear()
        self._order.clear()

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {"size": len(self._vecs), "maxsize": self.maxsize,
                "hits": self.hits, "misses": self.misses,
                "embed_calls": self.embed_calls,
                "hit_rate": self.hits / total if total else 0.0}


def test_cache_performance(cache_class: Callable, access_pattern: list[str], maxsize: int = 4) -> dict:
    """Test cache performance with given access pattern."""
    cache = cache_class(maxsize=maxsize)
    
    for text in access_pattern:
        # Simulate access: try get first, then put if miss
        result = cache.get(text)
        if result is None:
            # Mock embedding - in real usage this would be expensive
            vec = [0.5] * 10  # Mock 10-dimensional vector
            cache.put(text, vec)
    
    return cache.stats()


def main():
    """Run experiment comparing FIFO vs LRU performance."""
    print("🧪 LRU Cache Experiment - Catalyst Research")
    print("=" * 50)
    
    # Test patterns with different access characteristics
    test_cases = [
        {
            "name": "Sequential access",
            "pattern": ["A", "B", "C", "D", "E", "A", "B", "C"],
            "description": "Items accessed in order, no temporal locality"
        },
        {
            "name": "Temporal locality (recently used)",
            "pattern": ["A", "B", "C", "D", "A", "B", "C", "A"],
            "description": "Items frequently accessed recently"
        },
        {
            "name": "Temporal locality (distant)",
            "pattern": ["A", "B", "C", "D", "E", "F", "A", "B"],
            "description": "Items accessed after long gaps"
        },
        {
            "name": "Random access",
            "pattern": ["C", "A", "E", "B", "D", "A", "E", "C", "B", "D"],
            "description": "Random access pattern"
        }
    ]
    
    maxsize = 4  # Small cache to force evictions
    
    print(f"Cache size: {maxsize}")
    print(f"Testing {len(test_cases)} access patterns...\n")
    
    results = []
    
    for test_case in test_cases:
        print(f"📊 {test_case['name']}:")
        print(f"   Description: {test_case['description']}")
        print(f"   Pattern: {' → '.join(test_case['pattern'])}")
        
        # Test FIFO
        fifo_stats = test_cache_performance(SidechannelCacheFIFO, test_case['pattern'], maxsize)
        fifo_hit_rate = fifo_stats['hit_rate']
        
        # Test LRU
        lru_stats = test_cache_performance(SidechannelCacheLRU, test_case['pattern'], maxsize)
        lru_hit_rate = lru_stats['hit_rate']
        
        improvement = (lru_hit_rate - fifo_hit_rate) / fifo_hit_rate * 100 if fifo_hit_rate > 0 else 0
        
        result = {
            "test_case": test_case['name'],
            "fifo_hit_rate": fifo_hit_rate,
            "lru_hit_rate": lru_hit_rate,
            "improvement_pct": improvement,
            "fifo_stats": fifo_stats,
            "lru_stats": lru_stats
        }
        results.append(result)
        
        print(f"   FIFO hit rate: {fifo_hit_rate:.2%}")
        print(f"   LRU hit rate:  {lru_hit_rate:.2%}")
        print(f"   Improvement:    {improvement:+.1f}%")
        print()
    
    # Summary
    total_improvement = sum(r['improvement_pct'] for r in results)
    avg_improvement = total_improvement / len(results)
    
    print("📈 Summary:")
    print(f"Average improvement: {avg_improvement:+.1f}%")
    print(f"Cases where LRU won: {sum(1 for r in results if r['improvement_pct'] > 0)}/{len(results)}")
    
    positive_improvements = [r for r in results if r['improvement_pct'] > 0]
    if positive_improvements:
        avg_positive = sum(r['improvement_pct'] for r in positive_improvements) / len(positive_improvements)
        print(f"Average improvement when positive: {avg_positive:.1f}%")
    
    # Decision
    if avg_improvement > 0:
        print("✅ Result: LRU shows improvement over FIFO - RECOMMEND implementing")
        status = "keep"
    else:
        print("❌ Result: LRU does not show improvement - REJECT")
        status = "reject"
    
    # Record experiment
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    experiment_data = {
        "timestamp": timestamp,
        "experiment": "LRU vs Cache Performance",
        "status": status,
        "avg_improvement_pct": round(avg_improvement, 2),
        "test_cases": len(test_cases),
        "results": results
    }
    
    print(f"\n📝 Experiment recorded at: {timestamp}")
    print(f"Status: {status.upper()}")
    
    return experiment_data


if __name__ == "__main__":
    main()
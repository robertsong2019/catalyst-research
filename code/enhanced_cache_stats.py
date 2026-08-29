"""Enhanced Cache Statistics Experiment for Catalyst Research

Experiment #2: Add detailed statistics and analytics to SidechannelCache
Hypothesis: Enhanced statistics will provide better insights for cache optimization
Time budget: 30 minutes (Cycle 2)

Methodology:
1. Add detailed access pattern tracking
2. Add heat map of frequently accessed items
3. Add eviction analysis
4. Add performance recommendations
5. Test enhanced functionality

Metric: Information quality - better insights for cache optimization
"""

import hashlib
import time
from collections import defaultdict, OrderedDict
from typing import Any, Callable, Dict, List, Tuple
import json


class SidechannelCacheEnhanced:
    """SidechannelCache with enhanced statistics and analytics."""

    def __init__(self, maxsize: int = 8192):
        self._vecs: dict[str, list[float]] = {}
        self._order: list[str] = []        # FIFO eviction order
        self.maxsize = maxsize
        
        # Basic counters
        self.hits = 0
        self.misses = 0
        self.embed_calls = 0
        
        # Enhanced statistics
        self._access_times: Dict[str, List[float]] = defaultdict(list)
        self._access_frequency: Dict[str, int] = defaultdict(int)
        self._eviction_count = 0
        self._last_eviction_time = 0
        self._hit_heat_map: Dict[str, int] = defaultdict(int)
        self._miss_heat_map: Dict[str, int] = defaultdict(int)
        
        # Performance tracking
        self._total_get_time = 0
        self._total_put_time = 0
        self._start_time = time.time()

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> list[float] | None:
        """Get vector with enhanced tracking."""
        start_time = time.time()
        key = self._key(text)
        
        if key in self._vecs:
            self.hits += 1
            self._access_frequency[key] += 1
            self._hit_heat_map[key] += 1
            self._access_times[key].append(time.time())
            
            result = self._vecs[key]
            
            # Track performance
            get_time = time.time() - start_time
            self._total_get_time += get_time
            
            return result
        else:
            self.misses += 1
            self._miss_heat_map[key] += 1
            get_time = time.time() - start_time
            self._total_get_time += get_time
            return None

    def put(self, text: str, vec: list[float]) -> None:
        """Put vector with enhanced tracking."""
        start_time = time.time()
        key = self._key(text)
        
        if key not in self._vecs:
            self._order.append(key)
            if len(self._order) > self.maxsize:
                # Track eviction
                oldest_key = self._order.pop(0)
                self._vecs.pop(oldest_key, None)
                self._eviction_count += 1
                self._last_eviction_time = time.time()
                
                # Transfer heat map data
                if oldest_key in self._hit_heat_map:
                    del self._hit_heat_map[oldest_key]
                if oldest_key in self._access_times:
                    del self._access_times[oldest_key]
                if oldest_key in self._access_frequency:
                    del self._access_frequency[oldest_key]
                
        self._vecs[key] = list(vec)
        
        # Track performance
        put_time = time.time() - start_time
        self._total_put_time += put_time

    def forget(self) -> None:
        """Drop all vectors, enhanced tracking included."""
        self._vecs.clear()
        self._order.clear()
        
        # Reset enhanced stats but keep basic counters for audit
        self._access_times.clear()
        self._access_frequency.clear()
        self._hit_heat_map.clear()
        self._miss_heat_map.clear()
        self._eviction_count = 0
        self._last_eviction_time = 0
        self._total_get_time = 0
        self._total_put_time = 0

    def stats(self) -> dict:
        """Return basic cache statistics."""
        total = self.hits + self.misses
        return {"size": len(self._vecs), "maxsize": self.maxsize,
                "hits": self.hits, "misses": self.misses,
                "embed_calls": self.embed_calls,
                "hit_rate": self.hits / total if total else 0.0}

    def enhanced_stats(self) -> dict:
        """Return enhanced statistics and analytics."""
        total = self.hits + self.misses
        
        # Calculate hit/heat ratios
        total_heat = sum(self._hit_heat_map.values()) + sum(self._miss_heat_map.values())
        hit_heat_ratio = sum(self._hit_heat_map.values()) / total_heat if total_heat > 0 else 0
        
        # Most frequently accessed items
        top_accessed = sorted(self._access_frequency.items(), 
                            key=lambda x: x[1], reverse=True)[:10]
        
        # Most "hot" items (high hit frequency)
        top_hot = sorted(self._hit_heat_map.items(), 
                        key=lambda x: x[1], reverse=True)[:10]
        
        # Calculate eviction efficiency
        eviction_efficiency = (self._eviction_count / self.maxsize) if self.maxsize > 0 else 0
        
        # Performance metrics
        uptime = time.time() - self._start_time
        avg_get_time = self._total_get_time / max(self.hits + self.misses, 1)
        avg_put_time = self._total_put_time / max(len(self._vecs), 1)
        
        # Access pattern analysis
        recent_accesses = []
        now = time.time()
        for key, times in self._access_times.items():
            recent = [t for t in times if now - t < 60]  # Last minute
            if recent:
                recent_accesses.append((key, len(recent)))
        
        return {
            # Basic stats
            "basic_stats": self.stats(),
            
            # Access pattern analysis
            "total_accesses": total,
            "access_frequency": dict(self._access_frequency),
            "top_accessed": top_accessed,
            "recent_accesses": sorted(recent_accesses, key=lambda x: x[1], reverse=True)[:5],
            
            # Heat map analysis
            "hit_heat_ratio": hit_heat_ratio,
            "top_hot_items": top_hot,
            "heat_map": dict(self._hit_heat_map),
            
            # Eviction analysis
            "eviction_count": self._eviction_count,
            "eviction_efficiency": eviction_efficiency,
            "last_eviction_time": self._last_eviction_time,
            
            # Performance metrics
            "uptime_seconds": uptime,
            "avg_get_time_ms": avg_get_time * 1000,
            "avg_put_time_ms": avg_put_time * 1000,
            "total_get_time_ms": self._total_get_time * 1000,
            "total_put_time_ms": self._total_put_time * 1000,
            
            # Recommendations
            "recommendations": self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on statistics."""
        recommendations = []
        
        # Hit rate analysis
        hit_rate = self.stats()['hit_rate']
        if hit_rate < 0.5:
            recommendations.append("❌ Low hit rate (<50%) - consider increasing cache size")
        elif hit_rate > 0.8:
            recommendations.append("✅ High hit rate (>80%) - cache size is well-tuned")
        
        # Eviction analysis
        eviction_rate = self._eviction_count / max(len(self._order), 1)
        if eviction_rate > 0.9:
            recommendations.append("⚠️ High eviction rate (>90%) - consider increasing cache size")
        elif eviction_rate < 0.1:
            recommendations.append("✅ Low eviction rate (<10%) - cache size may be too large")
        
        # Hot item analysis
        if self._hit_heat_map:
            max_heat = max(self._hit_heat_map.values())
            avg_heat = sum(self._hit_heat_map.values()) / len(self._hit_heat_map)
            if max_heat > avg_heat * 3:
                recommendations.append("🔥 Hot items detected - consider prefetching frequently accessed items")
        
        # Performance analysis
        if self._total_get_time > 0:
            get_overhead = self._total_get_time / max(self.hits + self.misses, 1)
            if get_overhead > 0.001:  # >1ms average get time
                recommendations.append("⚡ High get overhead (>1ms) - optimize data structures")
        
        return recommendations

    def export_report(self, filename: str = None) -> str:
        """Export detailed statistics report as JSON."""
        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cache_type": "SidechannelCacheEnhanced",
            "maxsize": self.maxsize,
            "enhanced_stats": self.enhanced_stats()
        }
        
        if filename:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
        
        return json.dumps(report, indent=2)


def test_enhanced_cache():
    """Test the enhanced cache functionality."""
    print("🧪 Enhanced Cache Statistics Experiment")
    print("=" * 50)
    
    # Create enhanced cache
    cache = SidechannelCacheEnhanced(maxsize=4)
    
    # Simulate realistic access pattern
    test_data = [
        "user_session_1_message_1",
        "user_session_1_message_2", 
        "user_session_2_message_1",
        "user_session_1_message_1",  # Repeat
        "user_session_3_message_1",
        "user_session_1_message_2",  # Repeat
        "user_session_1_message_1",  # Repeat
        "user_session_4_message_1",
        "user_session_2_message_1",  # Repeat
    ]
    
    print("📝 Simulating access pattern...")
    for i, text in enumerate(test_data):
        # Simulate get operation
        result = cache.get(text)
        if result is None:
            # Simulate embedding and put
            vec = [0.5] * 10  # Mock 10D vector
            cache.put(text, vec)
        
        if i < 3:  # Show first few operations
            print(f"   {i+1}. {text[:20]}... -> {'HIT' if result is not None else 'MISS'}")
    
    print("\n📊 Basic Statistics:")
    basic = cache.stats()
    for key, value in basic.items():
        print(f"   {key}: {value}")
    
    print("\n🔍 Enhanced Statistics:")
    enhanced = cache.enhanced_stats()
    
    print(f"   Total accesses: {enhanced['total_accesses']}")
    print(f"   Hit heat ratio: {enhanced['hit_heat_ratio']:.2%}")
    print(f"   Eviction count: {enhanced['eviction_count']}")
    print(f"   Avg get time: {enhanced['avg_get_time_ms']:.2f}ms")
    
    print("\n📈 Top accessed items:")
    for key, count in enhanced['top_accessed']:
        print(f"   {key[:16]}...: {count} accesses")
    
    print("\n🔥 Hot items:")
    for key, heat in enhanced['top_hot_items']:
        print(f"   {key[:16]}...: {heat} hits")
    
    print("\n💡 Recommendations:")
    for rec in enhanced['recommendations']:
        print(f"   {rec}")
    
    # Export report
    report = cache.export_report()
    print(f"\n📄 Report exported (JSON length: {len(report)} chars)")
    
    return enhanced


if __name__ == "__main__":
    test_enhanced_cache()
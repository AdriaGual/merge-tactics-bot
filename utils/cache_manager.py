"""
Cache management utilities for the Merge Tactics bot.
"""

import time
from config.constants import POSITION_CACHE_SIZE

class CacheManager:
    def __init__(self):
        self.position_cache = {}
        self.elixir_cache = {"value": None, "timestamp": 0}
        
    def get_position_cache_key(self, center):
        """Generate cache key for position"""
        return f"{center[0]}_{center[1]}"
        
    def cache_position(self, center, position):
        """Cache a position with size limit"""
        cache_key = self.get_position_cache_key(center)
        
        # Clear old entries if cache is too large
        if len(self.position_cache) >= POSITION_CACHE_SIZE:
            # Remove oldest 25% of entries
            items_to_remove = len(self.position_cache) // 4
            keys_to_remove = list(self.position_cache.keys())[:items_to_remove]
            for key in keys_to_remove:
                del self.position_cache[key]
                
        self.position_cache[cache_key] = position
        
    def get_cached_position(self, center):
        """Get cached position"""
        cache_key = self.get_position_cache_key(center)
        return self.position_cache.get(cache_key)
        
    def cache_elixir(self, value):
        """Cache elixir value with timestamp"""
        self.elixir_cache = {
            "value": value,
            "timestamp": time.time()
        }
        
    def get_cached_elixir(self, cache_duration):
        """Get cached elixir if still valid"""
        current_time = time.time()
        if (self.elixir_cache["value"] is not None and
            current_time - self.elixir_cache["timestamp"] < cache_duration):
            return self.elixir_cache["value"]
        return None
        
    def clear_caches(self):
        """Clear all caches"""
        self.position_cache.clear()
        self.elixir_cache = {"value": None, "timestamp": 0}

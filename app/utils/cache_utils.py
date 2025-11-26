from datetime import datetime, timedelta

_cache = {}

def cache_search(user_id, from_city, to_city, date, mode, trips):
    key = f"{user_id}:{from_city}:{to_city}:{date}:{mode}"
    _cache[key] = {"data": trips, "expires": datetime.utcnow() + timedelta(minutes=10)}

def get_cached_search(user_id, from_city, to_city, date, mode):
    key = f"{user_id}:{from_city}:{to_city}:{date}:{mode}"
    item = _cache.get(key)
    if item and item["expires"] > datetime.utcnow():
        return item["data"]
    return None

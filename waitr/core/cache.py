
cache_registry = {
    'active_connections': {},
    'ip_to_worker': {},
}

def get_cache(cache_name):
    if cache_name in cache_registry:
        return cache_registry[cache_name].items()
    else:
        print(f"Cache '{cache_name}' not found")
        return []

def get_cached_value(cache_name, key):
    return cache_registry.get(cache_name, {}).get(key, None)

def update_cache(cache_name, key, value):
    if cache_name in cache_registry:
        cache_registry[cache_name][key] = value
    else:
        print(f"Cache '{cache_name}' not found")

def delete_cached_value(cache_name, key):
    if cache_name not in cache_registry:
        print(f"Cache '{cache_name}' not found")
    else:
        cache = cache_registry[cache_name]
        cache.pop(key, None)

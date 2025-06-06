import tomllib

PATH_TO_CONFIG_FILE = "config/waitr.conf"

_config = None

def init_config():
    global _config
    with open(PATH_TO_CONFIG_FILE, "rb") as f:
        _config = tomllib.load(f)

def get_config():
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config

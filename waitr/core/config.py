import os
import sys
import tomllib
import logging

PATH_TO_CONFIG_FILE = "config/waitr.conf"
logger = logging.getLogger('waitr.core.config')

_config = None

def _fatal(msg: str) -> None:
    logger.critical(msg)
    logger.info('[M] Exiting...')
    sys.exit(1)

def init_config() -> None:
    global _config
    
    if _config is not None:
        logger.warning("Re-initialization attempt blocked: configuration is already set")
        return None

    if not os.path.isfile(PATH_TO_CONFIG_FILE):
        _fatal(f"[M] Config file not found: {PATH_TO_CONFIG_FILE}")

    try:
        logger.debug("[M] Trying to read and parse config file..")
        with open(PATH_TO_CONFIG_FILE, "rb") as f:
            _config = tomllib.load(f)
        logger.info("[M] Config file loaded and parsed")
    except PermissionError:
        _fatal(f"[M] Permission denied while reading config file: {PATH_TO_CONFIG_FILE}")
    except tomllib.TOMLDecodeError as e:
        _fatal(f"[M] Failed to parse config file {PATH_TO_CONFIG_FILE}: {e}")
    except OSError as e:
        _fatal(f"[M] Error reading config file: {e}")

def get_config() -> dict:
    if _config is None:
        _fatal("Configuration has not yet been initialized. That's strange.")
        return {} # unreachable, just for return type validation
    
    logger.debug("Config accessed.")
    return _config
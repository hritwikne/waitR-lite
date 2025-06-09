import os
import json
import logging.config

def setup_logging(default_path='config/logger.json', default_level=logging.INFO, env_key='LOG_CFG'):
    """
    Set up logging configuration from a JSON file.

    This function looks for a configuration file specified by the `env_key`
    environment variable. If not found, it falls back to `default_path`.
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    path = os.getenv(env_key, default_path)

    if os.path.exists(path):
        try:
            with open(path, 'rt') as f:
                config = json.load(f)
            logging.config.dictConfig(config)
            logging.info("[M] Logging configured successfully from %s", path)
        except Exception as e:
            logging.basicConfig(level=default_level)
            logging.error("Error loading logging config from %s. Falling back to basicConfig.", path, exc_info=True)
    else:
        logging.basicConfig(level=default_level)
        logging.warning("Logging config file not found at %s. Using basicConfig.", path)
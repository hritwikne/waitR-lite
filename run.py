from waitr.core import master
from waitr.utils.logger import setup_logging

if __name__ == "__main__":
  setup_logging()
  master.start()
import os
import logging.handlers
import logging

class Logger():

    def __init__(self, log_file, log_level):
        self.log_file = log_file
        self.log_level = log_level

        self.setup_logger()

    def setup_logger(self):
        log_path = os.path.dirname(self.log_file)
        
        if not os.path.exists(log_path):
            os.makedirs(log_path)

        handler = logging.handlers.WatchedFileHandler(self.log_file)
        formatter = logging.Formatter(fmt='[%(asctime)s - %(levelname)s]: %(message)s', datefmt='%Y-%m-%d %I:%M:%S %p %z %Z')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger()
        logger.setLevel(self.log_level)
        logger.addHandler(handler)

        logging.debug(f'Logging to file: {self.log_file}')
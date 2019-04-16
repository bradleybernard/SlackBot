from bot.slack import Slack
from bot.logger import Logger
from bot.configurator import Configurator

import os
import logging

class Bot():

    log_extension = 'log'
    config_extension = 'yaml'
    
    def __init__(self, log_file=None, log_level=None, config_file=None):
        if not log_file:
            log_file = self.default_file(self.log_extension)

        if not config_file:
            config_file = self.default_file(self.config_extension)

        self.logger = Logger(log_file=log_file, log_level=log_level)
        self.config = Configurator(config_file=config_file)

        config = self.config.config
        self.slack = Slack(token=config['slack']['token'], channel=config['slack']['channel'], username=config['slack']['username'], icon_url=config['slack']['icon_url'])

        if not self.config_setup(config):
            logging.error(f'Failed to parse required keys from config file')
            exit(1)

        self.run()
    
    def default_file(self, extension):
        base_path = os.path.dirname(os.path.realpath(__file__))
        return f'{base_path}/../{self.filename()}.{extension}'

    def filename(self):
        pass

    def config_setup(self, config):
        return True

    def run(self):
        pass
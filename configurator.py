import yaml
import traceback
import logging

class Configurator():

    def __init__(self, config_file):
        self.config_file = config_file
        self.config = None

        self.setup_config()

    def setup_config(self):
        try:
            with open(self.config_file, 'r') as stream:
                self.config = yaml.safe_load(stream)
                logging.debug(f'Finished parsing yaml: {self.config_file}')
        except Exception as e:
            logging.error(traceback.format_exc())
            exit(1)
        except yaml.YAMLError as e:
            logging.error(e)
            exit(1)

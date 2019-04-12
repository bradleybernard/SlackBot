from datetime import datetime as _datetime, timedelta
from slackclient import SlackClient
from pytz import timezone

import pytz
import yaml
import datetime
import logging
import logging.handlers
import os
import traceback
import sys

class Slack(object):

    def __init__(self, token, channel, username, icon_url):
        self.slack_client = None
        self.slack_channel_id = None

        self.slack_token = token
        self.slack_channel = channel
        self.slack_username = username
        self.slack_icon_url = icon_url

        self.setup_client()

    def setup_client(self):
        self.slack_client = SlackClient(self.slack_token)
        self.find_slack_channel()

    def find_slack_channel(self):        
        channels = self.slack_client.api_call(
            "conversations.list",
            types="public_channel,private_channel",
            exclude_archived=1
        )

        channel_id = None
        for channel in channels['channels']:
            if channel['name'] and channel['name'] == self.slack_channel:
                channel_id = channel['id']

        if channel_id is None:
            logging.error(f'Could not find channel: {self.slack_channel} from channel list')
            exit(1)

        self.slack_channel_id = channel_id
        logging.debug(f'Found Slack channel ID for channel: {self.slack_channel} = {self.slack_channel_id}')

    def send_message_to_channel(self, message=None, attachments=None, thread_ts=None):
        post_message = self.slack_client.api_call(
            "chat.postMessage",
            text=message,
            channel=self.slack_channel_id,
            as_user=False,
            unfurl_links=True,
            username=self.slack_username,
            icon_url=self.slack_icon_url,
            thread_ts=thread_ts,
            attachments=attachments
        )

        logging.debug(f'Slack message result: {post_message}')
        return post_message

class Logger(object):

    def __init__(self, log_file, log_level):
        self.log_file = log_file
        self.log_level = log_level

        self.setup_logger()

    def setup_logger(self):
        log_path = os.path.dirname(self.log_file)
        
        if not os.path.exists(log_path):
            os.makedirs(log_path)

        handler = logging.handlers.WatchedFileHandler(self.log_file)
        formatter = logging.Formatter(fmt="[%(asctime)s - %(levelname)s]: %(message)s", datefmt="%Y-%m-%d %I:%M:%S %p %z %Z")
        handler.setFormatter(formatter)
        
        logger = logging.getLogger()
        logger.setLevel(self.log_level)
        logger.addHandler(handler)

        logging.debug(f'Loging to file: {self.log_file}')


class Configurator(object):

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


class Bot(object):
    
    def __init__(self, log_file=None, log_level=None, config_file=None):
        if not log_file:
            log_file = os.path.dirname(os.path.realpath(__file__)) + '/' + self.filename() + '.log'

        if not config_file:
            config_file = os.path.dirname(os.path.realpath(__file__)) + '/' + self.filename() + '.yaml'

        self.logger = Logger(log_file=log_file, log_level=log_level)
        self.config = Configurator(config_file=config_file)

        config = self.config.config
        self.slack = Slack(token=config['slack']['token'], channel=config['slack']['channel'], username=config['slack']['username'], icon_url=config['slack']['icon_url'])

        if not self.config_setup(config):
            logging.error(f'Failed to parse required keys from config file')
            exit(1)

        self.run()

    def filename(self):
        pass

    def config_setup(self, config):
        return True

    def run(self):
        pass
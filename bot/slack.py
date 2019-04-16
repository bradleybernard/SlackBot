from slackclient import SlackClient

import logging

class Slack():

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
            'conversations.list',
            types='public_channel,private_channel',
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
            'chat.postMessage',
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
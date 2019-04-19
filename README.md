# About
SlackBot is a simple Python Slack bot with logging and customizable configuration via a YAML file.

# Usage
Create a subclass inheriting from `Bot` class. The `Bot` class gets the configuration from the same directory as the python script with 
the a filename of: `filename() + '.yaml'`. The yaml config needs to have the Slack API token, channel name, and bot information: bot username, bot icon.
The config can also hold other values, which can be parsed using the `config_setup()` function. 
After parsing the Slack information from the `Bot` parent class, it calls the `config_setup` method. 
Subclasses can override this method to do any special setup.


`sample_bot.py`
```python

from bot.bot import Bot

import os
import traceback
import click


class SampleBot(Bot):
  
  def __init__(self, log_file=None, log_level=None, config_file=None):
        self.api_secret = None
        super().__init__(log_file, log_level, config_file)
        
  def filename(self):
        return os.path.splitext(os.path.basename(__file__))[0]
        
  def config_setup(self, config):
        self.api_secret = config['oauth_secret']
        return self.api_secret

  def run(self):
        self.slack.send_message_to_channel(message='Simple bot is here!')
        
        
@click.command()
@click.option('--log-level', default='INFO')

def main(log_level):
    dinner_bot = SampleBot(log_level=log_level)

if __name__ == '__main__':
    main()

```

`sample_bot.yaml`
```yaml
oauth_secret: __super__secret__key
slack: 
  token: xoxb-__super__secret__slack__token 
  channel: general
  username: SampleBot
  icon_url: https://google.com/images/botImage
```

# Lifecycle
`Bot` class:
1. Initialize: `Bot.init()`
2. Setup logging handler
3. Parse YAML configuration file for Slack information
4. `config_setup()` to parse any additional configuration (return `False` if configuration is invalid, will throw in `Bot` class)
5. Run bot now that setup is complete: `Bot.run()` which should be overriden in subclass


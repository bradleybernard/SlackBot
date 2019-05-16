from bs4 import BeautifulSoup
from enum import IntEnum
from pytz import timezone
from bot.bot import Bot
from dinner_client import CafeClient

import requests
import datetime
import os
import traceback
import logging
import click

# Constants
C950 = "1544" 
JOURNEY_MARKETPLACE = C950 
 
C605 = "840" 
BRICK_MORTAR = C605 
 
C580 = "772" 
CAFE_ELEVATE = C580 
ELEVATE = C580 
 
C700N = "1624" 
NOSH = C700N 
 
C700M = "1623" 
MEZZOS = C700M 

SOUTH_BAY_CAFES = {
    '950': C950, 
    '605': C605, 
    '580': C580, 
    '700 Nosh': C700N, 
    '700 Mezzos': C700M,
}

class FoodBot(Bot):

    weekdays = IntEnum('weekdays', 'monday tuesday wednesday thursday friday saturday sunday', start=0)

    def __init__(self, log_file=None, log_level=None, config_file=None):
        self.food_searches = None
        super().__init__(log_file, log_level, config_file)

    def filename(self):
        return os.path.splitext(os.path.basename(__file__))[0]

    def config_setup(self, config):
        self.food_searches = list(map(lambda item: item.lower(), config['search']))
        return self.food_searches

    def run(self):
        self.fetch_todays_menu()
    
    def fetch_todays_menu(self):
        tz = timezone('US/Pacific')
        date = datetime.datetime.now(tz=tz)
        date = date.date()
        
        logging.info(f'Fetching menu for {date}: started')

        if date.weekday() > self.weekdays.friday.value:
            logging.info('Weekend, not scraping')
            exit(0)

        for (cafe, cafe_id) in SOUTH_BAY_CAFES.items():
            self.fetch_menu(cafe, cafe_id, date)
        
        logging.info(f'Fetching menu for {date}: completed')
    
    def fetch_menu(self, cafe, cafe_id, date):
        cafe_client = CafeClient(cafe_id)

        items = []
        for food in self.food_searches:
            find = cafe_client.find(food)
            if len(find) > 0:
                items += find

        for item in items:
            message = self.format_found_message(cafe, item, date)
            self.slack.send_message_to_channel(message)

    def format_found_message(self, cafe, item, date):
        date_text = date.strftime('%A, %Y-%m-%d')
        message = f'Found *{item["label"].lower()}* for {item["meal"].lower()} at {cafe} on {date_text}'
        return message

@click.command()
@click.option('--log-level', default='INFO')

def main(log_level):
    food_bot = FoodBot(log_level=log_level)

if __name__ == '__main__':
    main()

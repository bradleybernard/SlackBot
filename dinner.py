from bs4 import BeautifulSoup
from enum import IntEnum
from bot.bot import Bot
from pytz import timezone

from dinner_client import CafeClient
import requests
import datetime
import os
import click
import sqlite3
import traceback
import logging

class DinnerBot(Bot):

    weekdays = IntEnum('weekdays', 'monday tuesday wednesday thursday friday saturday sunday', start=0)

    def __init__(self, log_file=None, log_level=None, config_file=None):
        super().__init__(log_file, log_level, config_file)

    def filename(self):
        return os.path.splitext(os.path.basename(__file__))[0]

    def run(self):
        self.fetch_dinner_menu_for_today()

    def today_date(self):
        tz = timezone('US/Pacific')
        date = datetime.datetime.now(tz=tz)
        return date.date()

    def fetch_dinner_menu_for_today(self):
        date = self.today_date()
        
        logging.info(f'Fetching dinner menu for {date}: started')

        if date.weekday() >= self.weekdays.friday.value:
            logging.info('Not Mon-Thurs, not scraping')
            exit(0)

        self.fetch_menu(date)

        logging.info(f'Fetching dinner menu for {date}: completed')


    def fetch_menu(self, date):
        MEZZOS = '1623'
        cafe = CafeClient(MEZZOS)

        message = self.format_menu_items(cafe.get_dinner())
        self.slack.send_message_to_channel(message)
    
    def format_menu_items(self, menu_items):
        menu = f'Dinner menu for Mezzo today ({self.today_date()}): {self.url}\n'
        
        for menu_item in menu_items:
            menu += f' - *{self.capitalized(menu_item["label"])}*'

            if 'station' in menu_item and menu_item['station']:
                menu += f' - {self.capitalized(menu_item["station"])}'
            menu += '\n'
            if 'description' in menu_item and menu_item['description']:
                menu += f'{menu_item["description"]}\n'
            menu += '\n'
        menu += ''
        return menu
    
    def capitalized(self, sentence):
        return ' '.join(word[0].upper() + word[1:] for word in sentence.split())

@click.command()
@click.option('--log-level', default='INFO')

def main(log_level):
    dinner_bot = DinnerBot(log_level=log_level)

if __name__ == '__main__':
    main()

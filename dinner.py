from bs4 import BeautifulSoup
from enum import IntEnum
from bot.bot import Bot
from pytz import timezone

import requests
import datetime
import os
import click
import sqlite3
import traceback
import logging

class DinnerBot(Bot):

    headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'}
    meals = IntEnum('meals', 'breakfast lunch dinner', start=0)
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
        date_text = date.strftime('%Y-%m-%d')
        url = 'https://linkedin.cafebonappetit.com/cafe/mezzo/'
        logging.debug(f'Fetching dinner menu for: {url}')

        try:
            response = requests.get(url, headers=self.headers)
        except requests.exceptions.RequestException as e:
            logging.error(e)
            exit(1)
        except Exception as e:
            logging.error(traceback.format_exc())
            exit(1)

        self.parse_menu(response.text, date)

    def parse_menu(self, menu_response, date):
        soup = BeautifulSoup(menu_response, 'html.parser')

        dinner_element = soup.select('#dinner')[0]
        content = dinner_element.select('div.site-panel__daypart-tab-content-inner')[0]
        headerCount = 0

        menu_items = []
        for child in content.children:
            if headerCount == 2:
                break
            if child.name == 'h3':
                headerCount += 1
            elif child.name == 'div':
                header = child.select('header')[0]
                item = (' '.join(header.get_text().lower().split()))
                menu_items.append(item)

        message = self.format_menu_items(menu_items)
        self.slack.send_message_to_channel(message)

    def format_menu_items(self, menu_items):
        menu = f'Dinner menu for Mezzo today ({self.today_date()}): \n```'
        for menu_item in menu_items:
            menu += f' - {menu_item.title()}\n'
        menu += '```'
        return menu

@click.command()
@click.option('--log-level', default='INFO')

def main(log_level):
    dinner_bot = DinnerBot(log_level=log_level)

if __name__ == '__main__':
    main()

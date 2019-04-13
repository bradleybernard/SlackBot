from bs4 import BeautifulSoup
from enum import IntEnum
from pytz import timezone
from bot import Bot

import requests
import datetime
import os
import traceback
import logging
import click

class FoodBot(Bot):

    cafes = {
        '605': 'brick-mortar',
        '580': 'cafe-elevate',
        '700': 'mezzo',
        '950': 'journey'
    }

    headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'}

    meals = IntEnum('meals', 'breakfast lunch dinner', start=0)
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
        # self.fetch_tomorrows_menu()
        start = datetime.datetime.strptime('2019-04-04', '%Y-%m-%d')
        end = datetime.datetime.strptime('2019-04-23', '%Y-%m-%d')
        self.fetch_menu_date_range(start, end)

    def fetch_tomorrows_menu(self):
        tz = timezone('US/Pacific')
        date = datetime.datetime.now(tz=tz) + datetime.timedelta(days=1)
        date = date.date()
        
        logging.info(f'Fetching menu for {date}: started')

        if date.weekday() > self.weekdays.friday.value:
            logging.info('Weekend, not scraping')
            exit(0)

        for (cafe, cafe_url) in self.cafes.items():
            self.fetch_menu(cafe, cafe_url, date)

        logging.info(f'Fetching menu for {date}: completed')

    def fetch_menu_date_range(self, start, end):
        delta = end - start

        for current_date in range(delta.days + 1):
            date = start + datetime.timedelta(current_date)
            
            if date.weekday() > self.weekdays.friday.value:
                continue

            for (cafe, cafe_url) in self.cafes.items():
                self.fetch_menu(cafe, cafe_url, date)

    def fetch_menu(self, cafe, cafe_url, date):
        date_text = date.strftime('%Y-%m-%d')
        url = f'https://linkedin.cafebonappetit.com/cafe/{cafe_url}/{date_text}/'
        logging.debug(f'Fetching menu for: {url}')

        try:
            response = requests.get(url, headers=self.headers)
        except requests.exceptions.RequestException as e:
            logging.error(e)
            exit(1)
        except Exception as e:
            logging.error(traceback.format_exc())
            exit(1)

        self.parse_menu(cafe, response.text, date)

    def parse_menu(self, cafe, menu_response, date):
        soup = BeautifulSoup(menu_response, 'html.parser')
        panels = soup.select('div.c-tab__content--active')

        for (index, panel) in enumerate(panels):
            menu_items = panel.select('button.site-panel__daypart-item-title')
            for menu_item in menu_items:
                item_text = ' '.join(menu_item.get_text().lower().split())
                for food in self.food_searches:
                    if food in item_text:
                        meal = self.meals(index)
                        message = self.format_found_message(cafe, menu_item, item_text, meal, date)
                        self.slack.send_message_to_channel(message)

    def format_found_message(self, cafe, menu_item, item_text, meal, date):
        date_text = date.strftime('%A, %Y-%m-%d')
        message = f'Found *{item_text}* for {meal.name} at {cafe} on {date_text}'
        return message


@click.command()
@click.option('--log-level', default='INFO')

def main(log_level):
    food_bot = FoodBot(log_level=log_level)

if __name__ == '__main__':
    main()

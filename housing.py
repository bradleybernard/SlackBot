from craigslist import CraigslistHousing, requests_get, bs, RESULTS_PER_REQUEST, CraigslistBase
from urllib.parse import urljoin

from bot.bot import Bot
from sqlite3 import Error
from dateutil import parser
from enum import IntEnum
from motionless import DecoratedMap, AddressMarker, LatLonMarker, Color
from pytz import timezone

import logging
import datetime
import sqlite3
import click
import time
import os
import json
import math
import urllib.parse as urlparse

# Override to use https
CraigslistBase.url_templates = url_templates = {
    'base': 'https://%(site)s.craigslist.org',
    'no_area': 'https://%(site)s.craigslist.org/search/%(category)s',
    'area': 'https://%(site)s.craigslist.org/search/%(area)s/%(category)s'
}

class CraigslistHousingCustom(CraigslistHousing):

    tags = IntEnum('tags', 'rooms sqfeet availability', start=0) 
    posting = IntEnum('posting', 'postedtop postedbottom updated', start=0)

    def remove_prefix(self, text, prefix):
        if text.startswith(prefix):
            return text[len(prefix):]
        return text

    def customize(self, result, detail_soup): 
        self.parse_rooms_and_availability(result, detail_soup)
        self.parse_dates_and_times(result, detail_soup)
        self.parse_images(result, detail_soup)
        self.parse_body(result, detail_soup)
        self.parse_address(result, detail_soup)
        self.parse_data_accuracy(result, detail_soup)

    def parse_rooms_and_availability(self, result, detail_soup):
        result.update({'rooms': None, 'bathrooms': None, 'availability': None})
        housing_info = detail_soup.select('span.shared-line-bubble')
        for (index, element) in enumerate(housing_info):
            text = element.text.strip()
            if index == self.tags.rooms.value:
                rooms = text.split('/')
                result['bedrooms'] = rooms[0].strip()[:-2]
                result['bathrooms'] = rooms[1].strip()[:-2]
                result['rooms'] = text
            if index == self.tags.sqfeet.value:
                result['area'] = text
            if index == self.tags.availability.value:
                datetime = element['data-date']
                date = parser.parse(datetime)
                result['availability'] = date

    def parse_dates_and_times(self, result, detail_soup):
        result.update({'posted': None, 'updated': None})
        posting_info = detail_soup.select('p.postinginfo.reveal')
        for (index, element) in enumerate(posting_info):
            time = element.select('time')[0]
            datetime = time['datetime']
            date = parser.parse(datetime)
            if index == self.posting.postedbottom.value:
                result['posted'] = date
            if index == self.posting.updated.value:
                result['updated'] = date
    
    def parse_images(self, result, detail_soup):
        result.update({'image': None})
        image_info = detail_soup.select('div.swipe-wrap')
        if image_info:
            image_info = image_info[0]
            first_image = image_info.select('img')[0]
            result['image'] = first_image['src']

    def parse_body(self, result, detail_soup):
        result['body'] = self.remove_prefix(detail_soup.select('#postingbody')[0].text.strip(), 'QR Code Link to This Post').strip()
        
    def parse_address(self, result, detail_soup):
        result.update({'gaddress': None, 'gcoords': None})
        lat_long_address = detail_soup.select('p.mapaddress')
        if lat_long_address:
            map_link = lat_long_address[0].select('a')[0]
            self.parse_gmaps_link(result, map_link['href'])

    def parse_data_accuracy(self, result, detail_soup):
        map = detail_soup.find('div', {'id': 'map'})
        if map:
            result['map_accuracy'] = int(map.attrs['data-accuracy'])
        
    def parse_gmaps_link(self, result, link):
        last_slash = link.rfind('/')
        remaining = link[last_slash+1:]

        if '?' in remaining:
            parsedurl = urlparse.urlparse(link)
            query = urlparse.parse_qs(parsedurl.query)
            result['gaddress'] = query['q'][0]
        else:
            components = remaining.split(',')
            result['gcoords'] = {
                'lat': components[0][1:],
                'long': components[1]
            }

class HousingBot(Bot):

    # URL: https://sfbay.craigslist.org/search/sby/apa?sort=date&hasPic=1&bundleDuplicates=1&search_distance=5&postal=94041&min_price=2000&max_price=6000&min_bedrooms=3&min_bathrooms=2&availabilityMode=0&housing_type=6&sale_date=all+dates

    filters = {
        'min_price': 2000,
        'max_price': 6000,
        'housing_type': ['house'],
        'min_bedrooms': 3,
        'min_bathrooms': 2,
        'has_image': True,
        'bundle_duplicates': True,
        'zip_code': 94041,
        'search_distance': 5
    }

    def __init__(self, notify, db_file=None, log_file=None, log_level=None, config_file=None):
        if not db_file:
            db_file = os.path.dirname(os.path.realpath(__file__)) + '/' + self.filename() + '.db'

        self.db = SQL(db_file=db_file)
        self.notify = notify
        self.timezone = timezone('US/Pacific')

        self.google_api_key = None
        self.map_markers = None
        self.template = None

        super().__init__(log_file, log_level, config_file)

    def config_setup(self, config):
        self.google_api_key = config['google_api_key']
        self.map_markers = config['map_markers']
        self.template = config['template']
        return self.google_api_key
            
    def filename(self):
        return os.path.splitext(os.path.basename(__file__))[0]

    def run(self):
        self.db.open()
        self.db.create_table()
        self.fetch_housing()
        self.db.close()

    def fetch_housing(self):
        logging.info('Fetching craigslist housing')
        housing_query = CraigslistHousingCustom(site='sfbay', area='sby', category='apa', filters=self.filters, log_level=logging.INFO)
    
        for listing in housing_query.get_results(sort_by='newest', geotagged=False, include_details=False):
            if self.is_new_housing(listing):
                url = listing['url']
                logging.info(f'Found new craigslist house: {url}')

                self.fetch_more_details(housing_query, listing)
                logging.info('Fetched more details about the house')

                self.insert_housing(listing)
                logging.info('Inserted house into database')

                if self.notify:
                    attachment = self.format_attachment(listing)
                    message = self.slack.send_message_to_channel(attachments=attachment)
                    reply = self.generate_reply(listing)
                    slack_message = self.slack.send_message_to_channel(message=reply, thread_ts=message['ts'])
                    logging.info(f'Notified slack channel of listing')

    def fetch_more_details(self, housing_query, result):
        detail_soup = housing_query.fetch_content(result['url'])
        housing_query.customize(result, detail_soup)
        housing_query.geotag_result(result, detail_soup)

    def is_new_housing(self, listing):
        # return self.db.count_by_craigslist_id_or_name(craigslist_id=listing['id'], name=listing['name']) == 0
        return self.db.count_by_craigslist_id_or_name(craigslist_id=listing['id'], name='poop') == 0

    def insert_housing(self, listing):
        row = (listing['id'], listing['name'], listing['url'], self.listing_insert_time(listing), int(time.time()))
        self.db.insert_housing_listing(row)

    def format_message(self, listing):
        color = self.listing_color_name(listing)
        name = listing['name']
        price = listing['price']
        url = listing['url']
        return f'[{color}] {name} - {price}: {url}'

    def listing_color(self, listing):
        colors = {
            'unknown': '#FFFFFF',
            'green': '#008000',
            'orange': '#FFA500',
            'red': '#FF0000',
        }

        price_per_person = self.price_per_person(listing)

        if price_per_person < 0:
            return colors['unknown']
        elif price_per_person > 700 and price_per_person <= 1200:
            return colors['green']
        elif price_per_person > 1200 and price_per_person <= 1500:
            return colors['orange']
        else:
            return colors['red']

    def listing_color_name(self, listing):
        price_per_person = self.price_per_person(listing)

        if price_per_person < 0:
            return 'Unknown'
        elif price_per_person > 700 and price_per_person <= 1200:
            return 'Green'
        elif price_per_person > 1200 and price_per_person <= 1500:
            return 'Orange'
        else:
            return 'Red'

    def price_per_person(self, listing):
        price = float(listing['price'][1:])
        bedrooms = float(listing['bedrooms'])
        bathrooms = float(listing['bathrooms'])

        # bathrooms is zero 
        if math.isclose(bathrooms, 0):
            return price / bedrooms
        
        #price per person = price / ((0.7 * beds) + (0.3 * baths))
        return (price / ((0.7 * bedrooms) + (0.3 * bathrooms)))
    
    def listing_insert_time(self, listing):
        return int(parser.parse(listing['datetime']).timestamp())

    def listing_time(self, listing):
        if listing['updated']:
            return int(listing['updated'].timestamp())
        elif listing['posted']:
            return int(listing['posted'].timestamp())
        else:
            return 'N/A'
        
    def listing_availability(self, listing):
        if listing['availability']:
            if listing['availability'] <= datetime.datetime.now():
                return 'Now'
            else:
                return listing['availability'].strftime('%b %d')
        return 'N/A'

    def listing_area(self, listing):
        if listing['area']:
            return listing['area'][:-3]
        return 'N/A'

    def create_map_url(self, listing):
        if not listing['gaddress'] and not listing['geotag']:
            return None

        road_styles = [{
            'feature': 'road.highway',
            'element': 'geomoetry',
            'rules': {
                'visibility': 'simplified',
                'color': '#c280e9'
            }
        }, {
            'feature': 'transit.line',
            'rules': {
                'visibility': 'simplified',
                'color': '#bababa'
            }
        }]

        dmap = DecoratedMap(style=road_styles,key=self.google_api_key)
        for marker in self.map_markers:
            dmap.add_marker(AddressMarker(marker['address'], label=marker['label']))
        
        if listing['gaddress'] and listing['map_accuracy'] <= 10:
            dmap.add_marker(AddressMarker(listing['gaddress'], label='1', color='blue'))
        elif listing['geotag']:
            dmap.add_marker(LatLonMarker(listing['geotag'][0], listing['geotag'][1], label='0', color='blue'))

        return dmap.generate_url()

    def map_title(self, listing):
        if not listing['gaddress'] and not listing['geotag']:
            return None

        if listing['gaddress'] and listing['map_accuracy'] <= 10:
            return f'Provided address'

        if listing['geotag']:
            return f'Approximate location via map area'

    def map_text(self, listing):
        if not listing['gaddress'] and not listing['geotag']:
            return None

        if listing['gaddress'] and listing['map_accuracy'] <= 10:
            return listing['gaddress'].title()

        if listing['geotag']:
            latitude = listing['geotag'][0]
            longitude = listing['geotag'][1]
            return f'(latitude: {latitude}, longitude: {longitude})'

    def generate_reply(self, listing):
        day = datetime.datetime.now(tz=self.timezone).strftime('%A')
        listing_url = listing['url']
        friends_count = listing['bedrooms']

        template = self.template
        template = template.replace('{{day}}', day)
        template = template.replace('{{listing_url}}', listing_url)
        template = template.replace('{{friends_count}}', friends_count)
        template = template.replace('{{n}}', '\n')

        return f'``` \n{template}\n ```'


    def format_attachment(self, listing):

        map_url = self.create_map_url(listing)

        attachments = [{
            'fallback': self.format_message(listing),
            'color': self.listing_color(listing),
            'title': '[' + self.listing_color_name(listing) + '] ' + listing['name'],
            'title_link': listing['url'],
            'image_url': listing['image'],
            'text': listing['body'],
            'thumb_url': map_url,
            'fields': [
                {
                    'title': 'Bedrooms / Baths',
                    'value': listing['rooms'],
                    'short': True,
                },
                {
                    'title': 'Price',
                    'value': listing['price'],
                    'short': True,
                },
                {
                    'title': 'Location',
                    'value': listing['where'].capitalize(),
                    'short': True
                },
                {
                    'title': 'Sq Foot',
                    'value': self.listing_area(listing),
                    'short': True
                },
                {
                    'title': 'Available',
                    'value': self.listing_availability(listing),
                    'short': True
                },
                {
                    'title': 'Posted',
                    'value': listing['posted'].strftime('%b %d %I:%M %p %Z'),
                    'short': True
                }
            ],
            'footer': 'Craigslist Search',
            'footer_icon': 'http://files.softicons.com/download/social-media-icons/colored-pen-web-icons-by-iconexpo.com/png/256/craigslist-pen.png',
            'ts': self.listing_time(listing)
        }]

        if map_url:
            attachments.append({
                'image_url': map_url,
                'color': self.listing_color(listing),
                'title': self.map_title(listing),
                'text': self.map_text(listing),
                'footer': 'Google Maps',
            })

        return json.dumps(attachments)

class SQL(object):

    create_statement = """
        CREATE TABLE IF NOT EXISTS craigslist_housing (
            craigslist_id TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            craigslist_date INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            UNIQUE (craigslist_id)
        );
    """

    def __init__(self, db_file):
        self.db_file = db_file

    def open(self):
        try:
            logging.debug(f'Trying to create connection from file: {self.db_file}')
            self.connection = sqlite3.connect(self.db_file)
            logging.debug(f'Created connection: {self.connection}')
        except Error as e:
            logging.error(e)

    def close(self):
        logging.debug(f'Closing sqlite file: {self.db_file} connection: {self.connection}')
        self.connection.close()
        logging.debug(f'Closed sqlite file: {self.db_file} connection: {self.connection}')

    def create_table(self):
        try:
            cursor = self.connection.cursor()
            cursor.execute(self.create_statement)
        except Error as e:
            logging.error(e)

    def count_by_craigslist_id_or_name(self, craigslist_id, name):
        cursor = self.connection.cursor()
        cursor.execute('SELECT COUNT(rowid) FROM craigslist_housing WHERE craigslist_id = ? OR name = ?', (craigslist_id, name,))
        count = cursor.fetchone()[0]
        logging.debug(f'Count for ID = {craigslist_id} OR name = {name}: {count}')
        return count
            
    def insert_housing_listing(self, listing):
        insert = ''' INSERT INTO craigslist_housing (craigslist_id, name, url, craigslist_date, created_at) VALUES (?, ?, ?, ?, ?) '''
        cursor = self.connection.cursor()
        cursor.execute(insert, listing)
        self.connection.commit()
        logging.debug(f'Inserting listing: {listing}')
        return cursor.lastrowid
 
@click.command()
@click.option('--log-level', default='INFO')
@click.option('--notify/--no-notify', default=True)

def main(log_level, notify):
    housing_bot = HousingBot(log_level=log_level, notify=notify)

if __name__ == '__main__':
    main()
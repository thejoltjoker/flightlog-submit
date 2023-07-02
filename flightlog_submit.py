#!/usr/bin/env python3
"""flightlog_submit.py
Description of flightlog_submit.py.
"""
import logging
import os
import random
import re
import time
import requests
from xxhash import xxh3_64_hexdigest
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import tz
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()


class Tracklog:
    """
    A class representing a tracklog file.

    Attributes:
        path (Path): The path to the tracklog file.
        date (datetime): The date and time of the tracklog.
    """

    def __init__(self, path: Path):
        """
        Initializes a Tracklog object.

        Args:
            path (Path): The path to the tracklog file.
        """
        self.path = path

        # Add header data
        for key, value in parse_tracklog_header(self.path).items():
            setattr(self, key, value)

        self.date = datetime_from_igc(self.path)

    @property
    def date_string(self) -> str:
        """
        Returns the date and time of the tracklog as a formatted string.

        Returns:
            str: The formatted date and time string.
        """
        return self.date.strftime('%Y-%m-%d %H:%M')

    @property
    def checksum(self) -> str:
        """
        Returns the checksum of the tracklog file.

        Returns:
            str: The checksum of the tracklog file.
        """
        return xxh3_64_hexdigest(self.path.read_bytes(), seed=0)


class Pilot:
    """A class representing a pilot.
    """

    def __init__(self, pilot_id=None, glider_id=None, flightlog_username=None, flightlog_password=None):
        self.user_id = pilot_id or os.getenv('USER_ID')
        self.brandmodel_id = glider_id or os.getenv('BRANDMODEL_ID')
        self.flightlog_username = flightlog_username or os.getenv('FLIGHTLOG_USERNAME')
        self.flightlog_password = flightlog_password or os.getenv('FLIGHTLOG_PASSWORD')


class Endpoint:
    """
    A class representing endpoints for a flight log API.
    """

    url = 'https://flightlog.org'
    login = f'{url}/fl.html?l=1&a=37'

    @classmethod
    def options(cls, user_id):
        """
        Get the options endpoint URL for a specific user.

        Args:
            user_id (str): The user ID.

        Returns:
            str: The options endpoint URL.
        """
        return f'{cls.url}/fl.html?l=1&user_id={user_id}&a=102'

    @classmethod
    def new_flight(cls, user_id):
        """
        Get the new flight endpoint URL for a specific user.

        Args:
            user_id (str): The user ID.

        Returns:
            str: The new flight endpoint URL.
        """
        return f'{cls.url}/fl.html?l=1&user_id={user_id}&a=30'

    @classmethod
    def new_flight_tracklog(cls, user_id):
        """
        Get the new flight tracklog endpoint URL for a specific user.

        Args:
            user_id (str): The user ID.

        Returns:
            str: The new flight tracklog endpoint URL.
        """
        return f'{cls.url}/fl.html?l=1&user_id={user_id}&a=30&no_start=y'

    @classmethod
    def flights(cls, user_id, year=None):
        """
        Get the flights endpoint URL for a specific user and year.

        Args:
            user_id (str): The user ID.
            year (int, optional): The year. If not specified, the current year will be used.

        Returns:
            str: The flights endpoint URL.
        """
        if not year:
            year = datetime.today().year

        return f'https://flightlog.org/fl.html?l=1&user_id={user_id}&a=33&year={year}'


class FlightlogClient:
    """
    A client for interacting with the Flightlog.org API.

    Attributes:
        ENDPOINT (str): The base URL for Flightlog.org.
        pilot (Pilot): The pilot associated with the client.
        session (requests.sessions.Session): The session used for making HTTP requests.
    """

    ENDPOINT = 'https://flightlog.org/fl.html'

    def __init__(self, pilot: Pilot, session: requests.sessions.Session = None):
        """
        Initializes a FlightlogClient object.

        Args:
            pilot (Pilot): The pilot associated with the client.
            session (requests.sessions.Session): The session used for making HTTP requests.
        """
        self.pilot = pilot
        self.session = session or requests.Session()
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0'
        }

    def _get(self, url, params: dict = None, *args, **kwargs):
        """
        Sends a GET request to the specified URL with optional query parameters.

        Args:
            url (str): The URL to send the request to.
            params (dict): Optional query parameters for the request.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            requests.Response: The response object of the request.
        """
        # Set defaults
        params = params or {}
        default_params = {'l': 1}  # language 1:english
        for k, v in default_params.items():
            params.setdefault(k, v)

        return self.session.get(url, params=params, *args, **kwargs)

    def _post(self, url, params: dict = None, *args, **kwargs):
        """
        Sends a POST request to the specified URL with optional form data and query parameters.

        Args:
            url (str): The URL to send the request to.
            params (dict): Optional query parameters for the request.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            requests.Response: The response object of the request.
        """
        # Set defaults
        params = params or {}
        default_params = {'l': 1}  # language 1:english
        for k, v in default_params.items():
            params.setdefault(k, v)

        return self.session.post(url, params=params, *args, **kwargs)

    def login(self):
        """
        Logs in the pilot using the provided username and password.

        Returns:
            bool: True if the login was successful, False otherwise.
        """
        params = {'a': 37}  # login page

        data = {
            'login_name': self.pilot.flightlog_username,
            'pw': self.pilot.flightlog_password,
            'form': 'login',
            'url': '',
            'login': 'Sign+In'
        }

        # Get login page to set cookie
        self._get(self.ENDPOINT, params=params)

        # Post login
        response = self._post(self.ENDPOINT, data=data, params=params)

        # Check if successful
        if 'logout' in response.text:
            logger.debug(f'User #{self.pilot.user_id} logged in successfully')
            return True
        logger.warning(f'User #{self.pilot.user_id} failed to login')
        return False

    def flights(self, year=None):
        """
        Retrieve flight logs for a given year.

        Args:
            year (int): The year to retrieve flight logs for. If not specified, the current year will be used.

        Returns:
            list: A list of flight logs.
        """
        logs = []
        params = {'user_id': self.pilot.user_id,
                  'year': year or datetime.today().year,
                  'a': 33}
        response = self._get(self.ENDPOINT, params=params)

        if response.status_code == 200:
            # Parse the HTML response
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract the flight logs from the HTML
            td = soup.find_all('td')
            logs = [x.text.strip() for x in td if is_date_string(x.text.strip())]

        return logs

    def new_flight(self, tracklog: Tracklog):
        """
        Uploads a tracklog file to the flight log.

        Args:
            tracklog (Tracklog): The Tracklog object representing the tracklog file.

        Returns:
            requests.Response: The response object of the upload request.
        """
        params = {'a': 30,
                  'no_start': 'y',
                  'user_id': self.pilot.user_id}
        data = {
            'form': 'trip_form',
            'trip_id': '',
            'timestamp': '',
            'locked': '',
            'country_id': '0',
            'start': '',
            'tripdate_day': '',
            'tripdate_month': '',
            'tripdate_year': str(tracklog.date.year),
            'triptime_h': '',
            'triptime_m': '',
            'class_id': '1',
            'brandmodel_id': f"{self.pilot.brandmodel_id}",
            'brandmodel': '',
            'cnt': '0',
            'duration_h': '',
            'duration_m': '',
            'distance': '',
            'maxaltitude': '',
            'url': '',
            'description': '',
            'private': '',
            'save': 'Save'
        }
        files = {'tracklog': (
            tracklog.path.name,
            tracklog.path.read_bytes(),
            'application/octet-stream'
        ),
            'image': ('', '')
        }

        return self._post(self.ENDPOINT, params=params, files=files, data=data)


def time_string_to_datetime(time_string):
    """
    Converts a time string in the format 'HHMMSS' to a datetime object
    and adds two hours to it.

    Args:
        time_string (str): The time string to convert.

    Returns:
        datetime: The converted datetime object with two hours added.
    """

    # Convert the time string to a datetime object
    dt = datetime.strptime(time_string, '%H%M%S')

    # Add two hours to the datetime object
    dt_plus_two_hours = dt + timedelta(hours=2)

    return dt_plus_two_hours


def date_time_string_to_datetime(date_time_string: str) -> datetime:
    """
    Converts a date-time string in the format 'YYYY-MM-DD HH:MM' to a datetime object
    adjusted for the time zone difference between UTC and Europe/Stockholm.

    Args:
        date_time_string (str): The date-time string to convert.

    Returns:
        datetime: The converted datetime object adjusted for the time zone difference.
    """

    # Define the time zones
    from_zone = tz.gettz('UTC')
    to_zone = tz.gettz('Europe/Stockholm')

    # Convert the date-time string to a datetime object in UTC
    utc = datetime.strptime(date_time_string, '%Y-%m-%d %H:%M')

    # Set the time zone of the datetime object to UTC
    utc = utc.replace(tzinfo=from_zone)

    # Convert the time zone from UTC to Europe/Stockholm
    local = utc.astimezone(to_zone)

    return local


def xxhash(path: Path) -> str:
    """Get xxhash for a given path

    Args:
        path: Path to file

    Returns:
        str: 16-char long hash string
    """
    return xxh3_64_hexdigest(path.read_bytes(), seed=0)


def remove_duplicate_files(path: Path):
    """
    Remove duplicate files in a given directory path.

    Args:
        path (Path): The directory path to search for duplicate files.

    Returns:
        list: A list of Path objects representing the removed duplicate files.

    Example:
        path = Path('my_folder/')
        removed_files = remove_duplicate_files(path)
        for removed_file in removed_files:
            print(f"Removed file: {removed_file}")
    """
    hashes = {}
    removed = []
    files = path.rglob('*.*')
    # Iterate over files
    for f in files:
        # Get checksum
        checksum = xxhash(f)

        # Check if file hash already in list
        existing = hashes.get(checksum)
        if existing:
            # Unlink file with longest filename
            longest_filename = max([f, existing], key=lambda x: len(x.name))
            logger.info(f'Unlinking file {longest_filename.name}')
            removed.append(longest_filename)
            longest_filename.unlink()

        else:
            # Add checksum to dict
            hashes[checksum] = f

    return removed


def b_line_to_hours_minutes_seconds(b_line):
    """
    Convert a B-line string to hours and minutes.

    Args:
        b_line (str): The B-line string.

    Returns:
        tuple: A tuple containing the hours and minutes extracted from the B-line string.

    Example:
        b_line = '1234'
        hours, minutes = b_line_to_hours_minutes_seconds(b_line)
        print(f"Hours: {hours}, Minutes: {minutes}")  # Output: Hours: '12', Minutes: '34'
    """
    hours, minutes = b_line[:2], b_line[2:4]
    return hours, minutes


def parse_tracklog_line(line):
    """
    Parse a line from a tracklog and return a dictionary containing the parsed values.

    Args:
        line (str): The line from the tracklog to parse.

    Returns:
        dict: A dictionary containing the parsed values from the tracklog line.

    Example:
        line = "A21307015+000000+02300180000122"
        parsed_data = parse_tracklog_line(line)
        print(parsed_data)
        # Output: {'fix_time': '213070', 'latitude': 21.307015, 'longitude': 0.230018, 'pressure_altitude': 180,
                  'gps_altitude': 122, 'ground_speed': 180, 'track_angle': 1, 'fix_valid': True, 'num_satellites': 22}
    """
    log_dict = {'fix_time': line[1:7],
                'latitude': float(line[7:14]) / 100000,
                'longitude': float(line[15:23]) / 100000,
                'pressure_altitude': int(line[25:30]),
                'gps_altitude': int(line[30:35]),
                'ground_speed': int(line[35:40]),
                'track_angle': int(line[40:43]),
                'fix_valid': line[43] == 'A',
                'num_satellites': int(line[44:46])}

    return log_dict


def parse_tracklog_header(path: Path):
    """
    Parse the header information from a tracklog file and return a dictionary containing the parsed values.

    Args:
        path (Path): The path to the tracklog file.

    Returns:
        dict: A dictionary containing the parsed header information.

    Example:
        path = Path('tracklog.txt')
        header_data = parse_tracklog_header(path)
        print(header_data)
        # Output: {'date': '2023-07-02', 'pilot': 'John Doe', 'glider_type': 'Glider X', 'gps_datum': 'WGS84', 'firmware_version': '1.2.3', 'hardware_version': '2.0', 'flyskyhy_type': 'Type A', 'gps': 'Garmin', 'vario': 'XVario', 'competition_class': 'Open', 'time_zone': 'UTC+3', 'site': 'Mountain Peak'}
    """
    records = {
        'HFDTE': 'date',
        'HFFXA': 'fix_accuracy',
        'HFPLT': 'pilot',
        'HFCM2': 'second_pilot',
        'HFGTY': 'glider_type',
        'HFGID': 'glider_id',
        'HFDTM': 'gps_datum',
        'HFRFW': 'firmware_version',
        'HFRHW': 'hardware_version',
        'HFFTY': 'manufacturer_model',
        'HFGPS': 'gps',
        'HFPRS': 'pressure_sensor',
        'HFCID': 'competition_id',
        'HFCCL': 'competition_class',
        'HFTZN': 'time_zone',
        'HFSIT': 'site'
    }

    header = {}

    with path.open('r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            # Check if line starts with a header record
            if records.get(line[:5]):
                header[records.get(line[:5])] = line.split(':')[-1]

            # Special case for date because it doesn't use colon
            if line.startswith('HFDTE'):
                header['date'] = line[5:]

    return header


def sleep(min_sleep=9, max_sleep=31):
    """
    Sleeps for a random duration between min_sleep and max_sleep seconds.

    Args:
        min_sleep (int): The minimum duration in seconds. Defaults to 9.
        max_sleep (int): The maximum duration in seconds. Defaults to 31.
    """
    sleep_time = random.randint(min_sleep, max_sleep)
    logger.info(f'Sleeping for {sleep_time} seconds')
    time.sleep(sleep_time)


def parse_b_record(b_record):
    """B H H M M S S D D M MM MM N D D D M MM MM E V P P P P P G G G G G CR LF"""
    record = {
        'time_utc': b_record[1:7],
        'latitude': b_record[7:15],
        'longitude': b_record[15:24],
        'fix_validity': b_record[24],
        'press_alt': b_record[25:30],
        'gnss_alt': b_record[30:35],
        'fix_accuracy': b_record[35:38],
        'satellites_in_use': b_record[38:40],
        'engine_noise': b_record[40:43],
        'rpm': b_record[43:46],
        'carriage_return': b_record[46:48],
        'line_feed': b_record[48:50]
    }
    return record


def datetime_from_igc(path: Path):
    """
    Extract the datetime from an IGC file and return it as a datetime object.

    Args:
        path (Path): The path to the IGC file.

    Returns:
        datetime: A datetime object representing the datetime extracted from the IGC file.

    Example:
        path = Path('flight.igc')
        flight_datetime = datetime_from_igc(path)
        print(flight_datetime)
        # Output: 2023-07-02 10:30:45
    """
    timezone_offset = 0
    with path.open('r') as file:
        for line in file:
            line = line.strip()
            if line.startswith('HFDTE'):
                day, month, year = int(line[5:7]), int(line[7:9]), int(line[9:]) + 2000
            elif line.startswith('HFTZNTIMEZONE'):
                timezone_offset = int(line[14:])
            elif line.startswith('B'):
                hour, minute, second = int(line[1:3]), int(line[3:5]), int(line[5:7])
                hour += timezone_offset
                break

    return datetime(year, month, day, hour, minute, second)


def is_date_string(input_string):
    """
    Check if the input string matches the format 'YYYY-MM-DD HH:MM'.

    Args:
        input_string (str): The input string to be checked.

    Returns:
        bool: True if the input string matches the format, False otherwise.

    Example:
        input_str = '2023-07-02 10:30'
        is_date = is_date_string(input_str)
        print(is_date)
        # Output: True
    """
    regex = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}'
    return True if re.match(regex, input_string) else False


def main():
    """
    Main function for tracklog submission to flightlog.

    This function retrieves tracklogs from a specified path, checks if they are already registered on flightlog,
    and submits the new tracklogs. It adds a delay after each submission and maintains a skip list to avoid duplicates.
    """
    skip = []

    # Create a pilot from environment variables
    pilot = Pilot()

    # Path to tracklog files
    path = Path(os.getenv('TRACKLOG_PATH')) / str(datetime.now().year)

    # Remove duplicate logs before submitting
    remove_duplicate_files(path)

    while True:
        # Get tracklogs for upload
        tracklogs = sorted((Tracklog(f) for f in path.glob('*.IGC') if f.name not in skip), key=lambda x: x.path)

        if tracklogs:
            # Start new session
            with requests.Session() as s:
                # Init client
                flightlog = FlightlogClient(pilot, session=s)
                flightlog.login()
                flights = flightlog.flights()

                # For each tracklog, check if already registered
                for tracklog in tracklogs:
                    if tracklog.date_string not in flights:
                        # If new tracklog, submit
                        logger.info(f'Submitting {tracklog.path.name} to flightlog')
                        flightlog.new_flight(tracklog)

                        # Add delay after submission
                        sleep()
                    else:
                        logger.warning(f"Skipping {tracklog.path.name} because it's already on flightlog")

                    # Add to skip list
                    skip.append(tracklog.path.name)

        sleep()


if __name__ == '__main__':
    main()
    # TODO Add confirmation on upload
    
#!/usr/bin/env python

from meteofrance_api import MeteoFranceClient
import requests, time, datetime, dateutil.parser, os, re, logging, sched
from influxdb import InfluxDBClient

"""
  Weather Model (Providers provides what they can) that can be graphed
  - timestamp:int - data time
  - civilDaylight:boolean - if it's the day from civil twilights
  - temperature:float - temperature °c 1 decimal
  - humidity:int - humidity %
  - wind:int - Wind km/h
  - windGust:int - Wind Gust km/h
  - cloudiness:int - Cloudiness %
  - rain:float - rain mm/h 1 decimal
  - snow:float - like rain but for snow
  - icon:string - a full url for an icon
  - description: string - an human description
"""

class SunriseSunsetProvider():
    def current(self, latitude, longitude):
        resp = requests.get(
            'https://api.sunrise-sunset.org/json',
            params={'lat': latitude, 'lng': longitude, 'formatted': '0'}
        ).json()['results']

        logging.info('sunrisesunset current api response %s', resp)

        ts = int(round(time.time()))

        civilSunrise = int(datetime.datetime.timestamp(dateutil.parser.parse(resp['civil_twilight_begin'])))
        civilSunset = int(datetime.datetime.timestamp(dateutil.parser.parse(resp['civil_twilight_end'])))

        return {
            'timestamp': ts,
            'civilDaylight': True if ts > civilSunrise and ts < civilSunset else False
        }
    def forecast(self, latitude, longitude):
        return [] # I need not ahah

class MeteoFranceProvider():
    client = MeteoFranceClient()

    def current(self, latitude, longitude):
        return self.__map(self.__call(latitude, longitude, 'current'), 'current')
    def forecast(self, latitude, longitude):
        resp = self.__call(latitude, longitude, 'forecast')['forecast']

        values = []
        ts = int(round(time.time()))

        for hour_resp in resp:
            if hour_resp['dt'] > ts:
                values.append(self.__map(hour_resp, 'forecast'))

        return values
    def __map(self, resp, type):
        return {
            **{
                'timestamp': resp['dt'],
                'temperature': float(round(resp['T']['value'], 1)),
                'humidity': round(resp['humidity']),
                'wind': round(resp['wind']['speed'] * 3.6),
                'windGust': round(resp['wind']['gust'] * 3.6 if resp['wind']['gust'] != 0 else resp['wind']['speed'] * 3.6)
                # No other for current ... ???
            },
            **({
                'rain': float(round(
                    resp['rain'].get('1h', .0) or
                    resp['rain'].get('3h', .0) / 3 or
                    resp['rain'].get('6h', .0) / 6
                    , 1
                )),
                'snow': float(round(
                    resp['snow'].get('1h', .0) or
                    resp['snow'].get('3h', .0) / 3 or
                    resp['snow'].get('6h', .0) / 6
                    , 1
                )),
                'cloudiness': round(resp['clouds']),
                'icon': 'https://meteofrance.com/modules/custom/mf_tools_common_theme_public/svg/weather/%s.svg' % resp['weather']['icon'],
                'description': resp['weather']['desc']
            } if type == 'forecast' else {})
        }
    def __call(self, latitude, longitude, type):
        resp = self.client.session.request(
            'get',
            type,
            params={'lat': latitude, 'lon': longitude, 'lang': 'fr'},
        ).json()

        logging.info('meteofrance current api response %s', resp)

        return resp


class OpenWeatherMapProvider():
    def __init__(self, appid):
        self.appid = appid

    def current(self, latitude, longitude):
        return self.__map(self.__call(latitude, longitude, 'current'), 'current')
    def forecast(self, latitude, longitude):
        resp = self.__call(latitude, longitude, 'forecast')

        values = []

        for hour_resp in resp['list']:
            values.append(self.__map(hour_resp, 'forecast'))

        return values
    def __map(self, resp, type):
        return {
            'timestamp': resp['dt'],
            'temperature': float(round(resp['main']['temp'], 1)),
            'humidity': round(resp['main']['humidity']), # None in some cases ??? WTF Meteofrance
            'wind': round(resp['wind']['speed'] * 3.6),
            'windGust': round(resp['wind']['gust'] * 3.6 if 'gust' in resp['wind'] else resp['wind']['speed'] * 3.6),
            'cloudiness': round(resp['clouds']['all']),
            'icon': 'https://openweathermap.org/img/wn/%s@2x.png' % resp['weather'][0]['icon'],
            'description': resp['weather'][0]['description'],
            'rain': float(round(
                resp.get('rain', {}).get('rain1h', .0) or
                resp.get('rain', {}).get('rain3h', .0) / 3
              , 1
            )),
            'snow': float(round(
                resp.get('snow', {}).get('snow1h', .0) or
                resp.get('snow', {}).get('snow3h', .0) / 3
              , 1
            ))
        }
    def __call(self, latitude, longitude, type):
        resp = requests.get(
            'http://api.openweathermap.org/data/2.5/' + ('weather' if type == 'current' else 'forecast'),
            params={'appid': self.appid, 'units': 'metric', 'lat': latitude, 'lon': longitude, 'lang': 'fr'}
        ).json()

        logging.info('openweathermap current api response %s', resp)

        if int(resp.get('cod')) != 200:
            raise Exception('openweathermap error')

        return resp

class WeatherService():
    def __init__(self, providers):
        self.providers = providers

    def get_current(self, latitude, longitude):
        return self.__read('current', latitude, longitude)

    def get_forecast(self, latitude, longitude):
        return self.__read('forecast', latitude, longitude)

    # use of position object instead of three args ?
    def __read(self, type, latitude, longitude):
        values = {}

        for providerName in self.providers:
          try:
            values[providerName] = getattr(self.providers[providerName], type)(latitude, longitude)
          except Exception as e:
            logging.exception('Provider %s read error for type %s on coordinates %s %s', providerName, type, latitude, longitude)

        return values

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')

weather_service = WeatherService({
    'meteoFrance': MeteoFranceProvider(),
    'openWeatherMap': OpenWeatherMapProvider(os.environ['OPENWEATHERMAP_APPID']),
    'sunriseSunset': SunriseSunsetProvider()
})

seconds_per_unit = {"s": 1, "m": 60, "h": 3600}

def convert_to_seconds(duration):
    return int(duration[:-1]) * seconds_per_unit[duration[-1]]

locations = {}

for k, v in os.environ.items():
    if k[0:9] == 'LOCATION_':
        location = v.split(',')
        if len(location) != 2:
            raise Exception('Invalid lat long')
        locations[k[9:].lower()] = location

if not locations:
    raise Exception('Empty locations')

collect_frequency=os.environ['COLLECT_FREQUENCY_CURRENT']
collect_frequency_s=convert_to_seconds(collect_frequency)

collect_frequency_forecast=os.environ['COLLECT_FREQUENCY_FORECAST']
collect_frequency_forecast_s=convert_to_seconds(collect_frequency_forecast)

influxdb_client = InfluxDBClient(os.environ['INFLUXDB_HOST'], database=os.environ['INFLUXDB_DB'])
influxdb_measurement = os.environ['INFLUXDB_MEASUREMENT']

scheduler = sched.scheduler()

def collect(type, frequency):
    scheduler.enter(frequency, 1, collect, (type, frequency))
    logging.info('Collecting ' + type)

    for location, coordinates in locations.items():
        try:
            logging.info('Collecting location ' + location)
            weather = getattr(weather_service, 'get_' + type)(coordinates[0], coordinates[1])
            points = []

            for provider, values in weather.items():

                def value_to_point(value):
                    ts = value['timestamp']
                    del value['timestamp']

                    # AAAAAAAAAAAAAAAAH
                    for k, v in value.items():
                        if isinstance(v, int):
                            value[k] = float(v)

                    points.append({
                        'measurement': influxdb_measurement,
                        'tags': {
                          'provider': provider
                        },
                        'time': ts,
                        'fields': value
                    })

                if type == 'forecast':
                    for value in values:
                        value_to_point(value)
                else:
                    value_to_point(values)

            influxdb_client.write_points(points, tags={
                'location': location,
                'type': type
            }, time_precision='s')

            logging.info('Done')
        except Exception as e:
            logging.exception('Error collecting location %s for type %s (%s)', location, type, e)


collect('current', collect_frequency_s)
collect('forecast', collect_frequency_forecast_s)
scheduler.run()

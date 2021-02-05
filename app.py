#!/usr/bin/env python

from meteofrance_api import MeteoFranceClient
import requests, time, datetime, dateutil.parser, os, logging, socketserver, http.server, re, json
from cachetools import cached, TTLCache
from retrying import retry

class SunriseSunsetProvider():
    def current(self, latitude, longitude):
        resp = self.__api(latitude, longitude)

        ts = int(round(time.time()))

        civilSunrise = int(datetime.datetime.timestamp(dateutil.parser.parse(resp['civil_twilight_begin'])))
        civilSunset = int(datetime.datetime.timestamp(dateutil.parser.parse(resp['civil_twilight_end'])))

        return {
            'timestamp': ts,
            'civilDaylight': True if ts > civilSunrise and ts < civilSunset else False
        }
    def forecast(self, latitude, longitude):
        return [] # I need not ahah
    @cached(cache=TTLCache(maxsize=64, ttl=3600))
    def __api(self, latitude, longitude):
        resp = requests.get(
            'https://api.sunrise-sunset.org/json',
            params={'lat': latitude, 'lng': longitude, 'formatted': '0'},
            timeout=10
        ).json()['results']

        logging.info('sunrisesunset current api response %s', resp)

        return resp

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
                'temperature': round(resp['T']['value'], 1)
            },
            **({'humidity': resp['humidity']} if resp['humidity'] != None else {}),
            **({'wind': round(resp['wind']['speed'] * 3.6)} if resp['wind']['speed'] != None else {}),
            **({'windGust': round(resp['wind']['gust'] * 3.6 if (resp['wind']['gust'] != None and resp['wind']['gust'] != 0) else resp['wind']['speed'] * 3.6)} if resp['wind']['gust'] != None or resp['wind']['speed'] != None else {}),
            **({
                'rain': round(resp['rain'].get('1h', .0) or
                        resp['rain'].get('3h', .0) / 3 or
                        resp['rain'].get('6h', .0) / 6, 2)
                ,
                'snow': round(resp['snow'].get('1h', .0) or
                        resp['snow'].get('3h', .0) / 3 or
                        resp['snow'].get('6h', .0) / 6, 2)
                ,
                'cloudiness': resp['clouds'],
                'icon': 'https://meteofrance.com/modules/custom/mf_tools_common_theme_public/svg/weather/%s.svg' % resp['weather']['icon'],
                'description': resp['weather']['desc']
            } if type == 'forecast' else {})
        }
    def __call(self, latitude, longitude, type):
        resp = self.client.session.request(
            'get',
            type,
            params={'lat': latitude, 'lon': longitude, 'lang': 'fr'},
            timeout=10
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
            'temperature': round(resp['main']['temp'], 1),
            'humidity': resp['main']['humidity'], # None in some cases ??? WTF Meteofrance
            'wind': round(resp['wind']['speed'] * 3.6),
            'windGust': round(resp['wind']['gust'] * 3.6 if 'gust' in resp['wind'] else resp['wind']['speed'] * 3.6),
            'cloudiness': resp['clouds']['all'],
            'icon': 'https://openweathermap.org/img/wn/%s@2x.png' % resp['weather'][0]['icon'],
            'description': resp['weather'][0]['description'],
            'rain': round(resp.get('rain', {}).get('rain1h', .0) or
                    resp.get('rain', {}).get('rain3h', .0) / 3, 2)
            ,
            'snow': round(resp.get('snow', {}).get('snow1h', .0) or
                    resp.get('snow', {}).get('snow3h', .0) / 3, 2)
        }
    def __call(self, latitude, longitude, type):
        resp = requests.get(
            'http://api.openweathermap.org/data/2.5/' + ('weather' if type == 'current' else 'forecast'),
            params={'appid': self.appid, 'units': 'metric', 'lat': latitude, 'lon': longitude, 'lang': 'fr'},
            timeout=10
        ).json()

        logging.info('openweathermap current api response %s', resp)

        if int(resp.get('cod')) != 200:
            raise Exception('openweathermap error')

        return resp

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')

providers = {
    'meteo-france': MeteoFranceProvider(),
    'open-weather-map': OpenWeatherMapProvider(os.environ['OPENWEATHERMAP_APPID']),
    'sunrise-sunset': SunriseSunsetProvider()
}

@retry(wait_fixed=5000, stop_max_attempt_number=3, stop_max_delay=30000)
def query_provider(provider_name, type, latitude, longitude):
    if type == 'current':
        return providers[provider_name].current(latitude, longitude)

    return providers[provider_name].forecast(latitude, longitude)

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):

        if (self.path == '/favicon.ico'):
            print('Skipped')
            return

        component_match = re.match(r'^\/([\d.]+),([\d.]+)\/(current|forecast)\/([^?#]+)', self.path)

        if not component_match:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(bytes(str('Invalid request'), 'utf8'))
            return

        latitude, longitude, type, provider = component_match.groups()

        if provider not in providers:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(bytes(str('Unknown provider'), 'utf8'))
            return

        try:
            data = query_provider(provider, type, latitude, longitude)
            self.send_response(200)
            self.send_header('Content-type','application/json')
            self.end_headers()
            self.wfile.write(bytes(json.dumps(data), 'utf8'))
        except Exception as inst:
            self.send_response(500)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes(str(inst), 'utf8'))
            logging.exception('Request error')

httpd = socketserver.ThreadingTCPServer(('', 8080), Handler)
try:
   print('Listening')
   httpd.serve_forever()
except KeyboardInterrupt:
   pass
httpd.server_close()
print('Ended')

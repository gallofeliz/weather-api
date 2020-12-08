from meteofrance_api import MeteoFranceClient
import requests, time, datetime, dateutil.parser, socketserver, http.server, urllib.parse, json, os

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

        print('sunrisesunset current api response', resp)

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
                'temperature': round(resp['T']['value'], 1),
                'humidity': round(resp['humidity']),
                'wind': round(resp['wind']['speed'] * 3.6),
                'windGust': round(resp['wind']['gust'] * 3.6 if resp['wind']['gust'] != 0 else resp['wind']['speed'] * 3.6)
                # No other for current ... ???
            },
            **({
                'rain': round(
                    resp['rain'].get('1h', .0) or
                    resp['rain'].get('3h', .0) / 3 or
                    resp['rain'].get('6h', .0) / 6
                    , 1
                ),
                'snow': round(
                    resp['snow'].get('1h', .0) or
                    resp['snow'].get('3h', .0) / 3 or
                    resp['snow'].get('6h', .0) / 6
                    , 1
                ),
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

        print('meteofrance current api response', resp)

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
            'humidity': round(resp['main']['humidity']),
            'wind': round(resp['wind']['speed'] * 3.6),
            'windGust': round(resp['wind']['gust'] * 3.6 if 'gust' in resp['wind'] else resp['wind']['speed'] * 3.6),
            'cloudiness': round(resp['clouds']['all']),
            'icon': 'https://openweathermap.org/img/wn/%s@2x.png' % resp['weather'][0]['icon'],
            'description': resp['weather'][0]['description'],
            'rain': round(
                resp.get('rain', {}).get('rain1h', .0) or
                resp.get('rain', {}).get('rain3h', .0) / 3
              , 1
            ),
            'snow': round(
                resp.get('snow', {}).get('snow1h', .0) or
                resp.get('snow', {}).get('snow3h', .0) / 3
              , 1
            )
        }
    def __call(self, latitude, longitude, type):
        resp = requests.get(
            'http://api.openweathermap.org/data/2.5/' + ('weather' if type == 'current' else 'forecast'),
            params={'appid': self.appid, 'units': 'metric', 'lat': latitude, 'lon': longitude, 'lang': 'fr'}
        ).json()

        print('openweathermap current api response', resp)

        return resp

class WeatherService():
    def __init__(self, providers):
        self.providers = providers

    def get_current(self, latitude, longitude, location_alias):
        return self.__read('current', latitude, longitude, location_alias)

    def get_forecast(self, latitude, longitude, location_alias):
        return self.__read('forecast', latitude, longitude, location_alias)

    # use of position object instead of three args ?
    def __read(self, type, latitude, longitude, location_alias):
        values = {}
        errors = []

        for providerName in self.providers:
          try:
            values[providerName] = getattr(self.providers[providerName], type)(latitude, longitude)
          except Exception as e:
            print(str(e))
            errors.append(providerName)

        return {
          'type': type,
          'location': {
              'latitude': latitude,
              'longitude': longitude,
              'alias': location_alias
          },
          'values': values,
          'errors': errors
        }

weather = WeatherService({
    'meteoFrance': MeteoFranceProvider(),
    'openWeatherMap': OpenWeatherMapProvider(os.environ['OPENWEATHERMAP_APPID']),
    'sunriseSunset': SunriseSunsetProvider()
})

locations = {}

for k, v in os.environ.items():
    if k[0:9] == 'LOCATION_':
        location = v.split(',')
        if len(location) != 2:
            raise BaseException('Invalid lat long')
        locations[k[9:].lower()] = location

if not locations:
    raise BaseException('Empty locations')

default = os.environ.get('DEFAULT_LOCATION', list(locations.keys())[0])

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        sMac = urllib.parse.urlparse(self.path).path[1:]
        print('Requested ' + sMac)

        if (sMac == 'favicon.ico'):
            print('Skipped')
            return

        path_parts = sMac.split('/')

        print(path_parts)

        type = path_parts[0] if path_parts[0] != '' else 'current'
        location_alias = path_parts[1] if len(path_parts) > 1 else default

        if (type != 'current' and type != 'forecast'):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(bytes(str('Invalid type'), 'utf8'))
            return

        if (location_alias not in list(locations.keys())):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(bytes(str('Invalid location'), 'utf8'))
            return

        location = locations[location_alias]

        try:
            if type == 'current':
                data = weather.get_current(location[0], location[1], location_alias)
            else:
                data = weather.get_forecast(location[0], location[1], location_alias)
            self.send_response(200)
            self.send_header('Content-type','application/json')
            self.end_headers()
            self.wfile.write(bytes(json.dumps(data), 'utf8'))
        except Exception as inst:
            self.send_response(500)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes(str(inst), 'utf8'))
            print('ERROR ' + str(inst))

httpd = socketserver.TCPServer(('', 8080), Handler)
try:
   print('Listening')
   httpd.serve_forever()
except KeyboardInterrupt:
   pass
httpd.server_close()
print('Ended')

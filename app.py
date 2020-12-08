from meteofrance_api import MeteoFranceClient
import requests, time, datetime, dateutil.parser, socketserver, http.server, urllib.parse, json

"""
  Weather Model (Providers provides what they can)
  - timestamp:int - data time
  - civilDaylight:boolean - if it's the day from civil twilights
  - temperature:float - temperature °c 1 decimal
  - humidity:int - humidity %
  - wind:int - Wind km/h
  - windGust:int - Wind Gust km/h
  - cloudiness:int - Cloudiness %
  - rain1h/rain3h/rain6h:float - rain for 1h or 3h or 6h in mm 1 decimal
  - snow1h/snow3h/rain6h:float - like rain but for snow
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
                # Values depends on forecast granularity ; putting None to "unset" previous values (TODO check if relevant with my influxdb)
                'rain1h': round(resp['rain']['1h'], 1) if '1h' in resp['rain'] else None,
                'snow1h': round(resp['snow']['1h'], 1) if '1h' in resp['snow'] else None,
                'rain3h': round(resp['rain']['3h'], 1) if '3h' in resp['rain'] else None,
                'snow3h': round(resp['snow']['3h'], 1) if '3h' in resp['snow'] else None,
                'rain6h': round(resp['rain']['6h'], 1) if '6h' in resp['rain'] else None,
                'snow6h': round(resp['snow']['6h'], 1) if '6h' in resp['snow'] else None,
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
            **{
                'timestamp': resp['dt'],
                'temperature': round(resp['main']['temp'], 1),
                'humidity': round(resp['main']['humidity']),
                'wind': round(resp['wind']['speed'] * 3.6),
                'windGust': round(resp['wind']['gust'] * 3.6 if 'gust' in resp['wind'] else resp['wind']['speed'] * 3.6),
                'cloudiness': round(resp['clouds']['all']),
                'icon': 'https://openweathermap.org/img/wn/%s@2x.png' % resp['weather'][0]['icon'],
                'description': resp['weather'][0]['description']
            },
            **(
                # Missing value equals to 0
                {
                    'rain3h': round(resp['rain']['3h'], 1) if 'rain' in resp and '3h' in resp['rain'] else 0.00,
                    'snow3h': round(resp['snow']['3h'], 1) if 'snow' in resp and '3h' in resp['snow'] else 0.00
                }
                if type == 'forecast' else
                {
                    'rain1h': round(resp['rain']['1h'], 1) if 'rain' in resp and '1h' in resp['rain'] else 0.00,
                    'snow1h': round(resp['snow']['1h'], 1) if 'snow' in resp and '1h' in resp['snow'] else 0.00
                }
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
    'openWeatherMap': OpenWeatherMapProvider('xxx'),
    'sunriseSunset': SunriseSunsetProvider()
})

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        sMac = urllib.parse.urlparse(self.path).path[1:]
        print('Requested ' + sMac)

        if (sMac == 'favicon.ico'):
            print('Skipped')
            return

        if (sMac == ''):
            sMac = 'current'

        if (sMac != 'current' and sMac != 'forecast'):
            self.send_response(404)
            self.end_headers()

        try:
            if sMac == 'current':
                data = weather.get_current(49.1349243, 1.4400054, 'home')
            else:
                data = weather.get_forecast(49.1349243, 1.4400054, 'home')
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

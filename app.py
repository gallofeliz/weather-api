from meteofrance_api import MeteoFranceClient
import requests, time, datetime, dateutil.parser, socketserver, http.server, urllib.parse, json

class SunriseSunset():
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

class MeteoFranceWeather():
    def current(self, latitude, longitude):
        client = MeteoFranceClient()
        resp = client.session.request(
            'get',
            'current',
            params={'lat': latitude, 'lon': longitude, 'lang': 'fr'},
        ).json()

        print('meteofrance current api response', resp)

        return {
            'timestamp': resp['dt'],
            'temperature': round(resp['T']['value'], 1),
            'humidity': round(resp['humidity']),
            'wind': round(resp['wind']['speed'] * 3.6),
            'windGust': round(resp['wind']['gust'] * 3.6)
            # No other ...
        }

class OpenWeatherMap():
    def current(self, latitude, longitude):
        resp = requests.get(
            'http://api.openweathermap.org/data/2.5/weather',
            params={'appid': 'xxx', 'units': 'metric', 'lat': latitude, 'lon': longitude, 'lang': 'fr'}
        ).json()

        print('openweathermap current api response', resp)

        return {
            'timestamp': resp['dt'],
            'temperature': round(resp['main']['temp'], 1),
            'humidity': round(resp['main']['humidity']),
            'wind': round(resp['wind']['speed'] * 3.6),
            'windGust': round(resp['wind']['gust'] * 3.6 if 'gust' in resp['wind'] else resp['wind']['speed'] * 3.6),
            'cloudiness': round(resp['clouds']['all']),
            'rain1h': round(resp['rain']['1h'], 2) if 'rain' in resp and '1h' in resp['rain'] else 0.00,
            'snow1h': round(resp['snow']['1h'], 2) if 'snow' in resp and '1h' in resp['snow'] else 0.00,
            'icon': 'http://openweathermap.org/img/wn/%s@2x.png' % resp['weather'][0]['icon'],
            'desc': resp['weather'][0]['description']
        }

class Weather():
    def __init__(self, providers):
        self.providers = providers

    # use of position object instead of three args ?
    def __read(self, type, latitude, longitude, location_alias):
        values = {}
        errors = []

        for providerName in self.providers:
          try:
            values[providerName] = getattr(self.providers[providerName], type)(latitude, longitude)
          except Exception as e:
            print(e)
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

    def get_current(self, latitude, longitude, location_alias):
        return self.__read('current', latitude, longitude, location_alias)

    def get_forecast(self, latitude, longitude, location_alias):
        return self.__read('forecast', latitude, longitude, location_alias)


weather = Weather({
    'meteoFrance': MeteoFranceWeather(),
    'openWeatherMap': OpenWeatherMap(),
    'sunriseSunset': SunriseSunset()
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
                data = weather.get_current(49.1349243, 1.4400054, 'home')
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

httpd = socketserver.TCPServer(('', 8081), Handler)
try:
   print('Listening')
   httpd.serve_forever()
except KeyboardInterrupt:
   pass
httpd.server_close()
print('Ended')

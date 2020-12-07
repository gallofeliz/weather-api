from meteofrance_api import MeteoFranceClient
import requests

NAME='home'
LAT=49.1349243
LON=1.4400054
owmAppId = 'xxxxx'

#https://docs.breezometer.com/api-documentation/weather-api/v1/#example
#https://darksky.net/dev/docs
#https://api.meteo-concept.com/documentation#forecast-city-day

class MeteoFranceWeather():
    def current(self):
        client = MeteoFranceClient()
        resp = client.session.request(
            'get',
            'current',
            params={'lat': LAT, 'lon': LON, 'lang': 'fr'},
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
    def current(self):
        resp = requests.get(
            'http://api.openweathermap.org/data/2.5/weather',
            params={'appid': owmAppId, 'units': 'metric', 'lat': LAT, 'lon': LON, 'lang': 'fr'}
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
            'desc': resp['weather']['description']

            #daylight, sunset, sunrise
            # https://api.sunrise-sunset.org/json?formatted=0&lat=49.1349243&lng=1.4400054

            # ts = int(round(time.time()))
            # time_ = meteo['dt']

            # fields = get_fields_from_owm_entry(meteo)

            # suntimes = requests.get(
            #   'https://api.sunrise-sunset.org/json',
            #   params={'lat': '49.1326634', 'lng': '1.4417597', 'formatted': '0'}
            # ).json()['results']

            # sunrise = int(datetime.datetime.timestamp(dateutil.parser.parse(suntimes['civil_twilight_begin'])))
            # sunset = int(datetime.datetime.timestamp(dateutil.parser.parse(suntimes['civil_twilight_end'])))

            # day = True if ts > sunrise and ts < sunset else False

        }

meteofrance = MeteoFranceWeather()
openweathermap = OpenWeatherMap()

print({
    'type': 'current',
    'profile': NAME,
    'latitude': LAT,
    'longitude': LON,
    'meteofrance': meteofrance.current(),
    'openweathermap': openweathermap.current()
})

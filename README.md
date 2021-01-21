# weather-collector

For my use with influxdb and grafana, I wanted a agnostic API with ready to use data and multiple sources (meteofrance for wind gust for example, and other one for daylight)

`OPENWEATHERMAP_APPID=blabla LOCATION_HOLIDAYS=43.2149438,5.4297272 LOCATION_HOME=48.8793772,2.3429125 DEFAULT_LOCATION=home python3 app.py`

`sudo docker run --rm -p 8080:8080 -e OPENWEATHERMAP_APPID=blabla -e LOCATION_HOLIDAYS=43.2149438,5.4297272 -e LOCATION_HOME=48.8793772,2.3429125 -e DEFAULT_LOCATION=home weather` after build

## Output

```
{
    "type": "current",
    "location": {
        "latitude": "43.2149438",
        "longitude": "5.4297272",
        "alias": "holidays"
    },
    "values": {
        "meteoFrance": {
            "timestamp": 1607469480,
            "temperature": 4.7,
            "humidity": 75,
            "wind": 18,
            "windGust": 47
        },
        "openWeatherMap": {
            "timestamp": 1607469698,
            "temperature": 5.1,
            "humidity": 75,
            "wind": 23,
            "windGust": 42,
            "cloudiness": 48,
            "icon": "https://openweathermap.org/img/wn/03n@2x.png",
            "description": "partiellement nuageux",
            "rain": 0.0,
            "snow": 0.0
        },
        "sunriseSunset": {
            "timestamp": 1607469700,
            "civilDaylight": false
        }
    },
    "errors": []
}
```

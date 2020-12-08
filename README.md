# weather-api

For my use with influxdb and grafana, I wanted a agnostic API with ready to use data and multiple sources (meteofrance for wind gust for example, and other one for daylight)

`OPENWEATHERMAP_APPID=blabla LOCATION_HOLIDAYS=43.2149438,5.4297272 LOCATION_HOME=48.8793772,2.3429125 DEFAULT_LOCATION=home python3 app.py`

`sudo docker run --rm -p 8080:8080 -e OPENWEATHERMAP_APPID=blabla -e LOCATION_HOLIDAYS=43.2149438,5.4297272 -e LOCATION_HOME=48.8793772,2.3429125 -e DEFAULT_LOCATION=home weather` after build


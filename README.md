# weather-api

For my use with influxdb and grafana, I wanted a agnostic API with ready to use data and multiple sources (meteofrance for wind gust for example, and other one for daylight)

## How to run

See docker-compose

## How to call

Url template : http://localhost:8080/{lat},{lon}/{type}/{provider}

Example : http://localhost:8080/48.8583701,2.2922926/current/open-weather-map

## Response

Weather Model (Providers provide what they can) that can be graphed
  - timestamp:number - data time
  - temperature:number - temperature °c
  - humidity:number - humidity %
  - wind:number - Wind km/h
  - windGust:number - Wind Gust km/h
  - cloudiness:number - Cloudiness %
  - rain:number - rain mm/h
  - snow:number - like rain but for snow
  - icon:string - a full url for an icon
  - description: string - an human description
  - civilDaylight:boolean - if it's the day from civil twilights

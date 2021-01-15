FROM python:alpine

RUN pip install meteofrance_api python-dateutil influxdb

WORKDIR /app

ADD app.py .

CMD ./app.py

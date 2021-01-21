FROM python:alpine

RUN pip install meteofrance_api python-dateutil cachetools

WORKDIR /app

ADD app.py .

CMD ./app.py

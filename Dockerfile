FROM python:alpine

RUN pip install meteofrance_api python-dateutil cachetools retrying

WORKDIR /app

ADD app.py .

USER nobody

CMD ./app.py

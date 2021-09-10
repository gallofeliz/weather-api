FROM python:3.8-alpine3.12

RUN pip install meteofrance_api python-dateutil cachetools retrying

WORKDIR /app

ADD app.py .

USER nobody

CMD ./app.py

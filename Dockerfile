FROM python:alpine

RUN pip install meteofrance_api python-dateutil

WORKDIR /app

ADD app.py .

CMD ./app.py

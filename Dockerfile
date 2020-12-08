FROM python:alpine

RUN pip install meteofrance_api

WORKDIR /app

ADD app.py .

CMD ./app.py

FROM python:3.14.0-alpine3.22

WORKDIR /usr/src/app

ENV TZ="Europe/Berlin"

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

LABEL authors="Jason Bladt"

COPY ./app ./

CMD ["fastapi", "run", "./main.py"]

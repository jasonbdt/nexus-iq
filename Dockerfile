FROM python:3.13.0-alpine3.20

LABEL image.authors="Jason Bladt" \
      version="1.0.0"

WORKDIR /usr/src

RUN addgroup -S app && adduser -S app -G app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ./app app/
COPY ./ddragon ddragon/

RUN chown -R app:app /usr/src/app /usr/src/ddragon

EXPOSE 8000

USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/usr/src/app"]

FROM python:3.13.0-alpine3.20

LABEL image.authors="Jason Bladt" \
      version="1.0.0"

WORKDIR /usr/src

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# WORKDIR /usr/src/app

COPY ./app app/
EXPOSE 8000

USER guest

CMD ["uvicorn", "app.main:app", "--reload-dir", "/usr/src/app"]

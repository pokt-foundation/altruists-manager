FROM --platform=linux/amd64 python:3.11-bullseye

RUN apt update && \
    apt -y dist-upgrade && \
    apt install -y --no-install-recommends \
        tzdata \
        ca-certificates && \
    rm -rf /var/cache/apt/*

RUN pip install --upgrade pip

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt && \
    useradd --create-home appuser

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY ./app /app
WORKDIR /app

USER appuser
CMD ["gunicorn", "--conf", "/app/gunicorn_conf.py", "bb_exporter:app"]
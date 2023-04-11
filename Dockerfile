FROM --platform=linux/amd64 python:3.11-bullseye

RUN apt update && \
    apt -y dist-upgrade && \
    apt install -y --no-install-recommends \
        tzdata \
        ca-certificates && \
    rm -rf /var/cache/apt/* && \
    pip install --upgrade pip

RUN useradd --create-home appuser

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

USER appuser
COPY ./app /app
WORKDIR /app/altruists

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["python", "manage.py"]
CMD ["--help"]
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates gcc nginx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

RUN python -m evennia --init runtime

COPY overlay/ /app/runtime/
COPY railway_start.sh /app/railway_start.sh
COPY railway_settings.py /app/railway_settings.py
COPY nginx.conf /etc/nginx/nginx.conf
RUN chmod +x /app/railway_start.sh \
    && cat /app/railway_settings.py >> /app/runtime/server/conf/settings.py

EXPOSE 4001

CMD ["/app/railway_start.sh"]

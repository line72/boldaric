FROM python:3.11-slim-bookworm AS builder

RUN mkdir /tmp/boldaric
WORKDIR /tmp/boldaric
COPY pyproject.toml README.md MANIFEST.in ./
COPY boldaric/ ./boldaric/

RUN mkdir /opt/boldaric
RUN pip install --prefix=/opt/boldaric .

# Final Stage
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y supervisor

COPY --from=builder /opt/boldaric /opt/boldaric

# Set paths for binaries and Python packages
ENV PATH=/opt/boldaric/bin:$PATH
ENV PYTHONPATH=/opt/boldaric/lib/python3.11/site-packages

WORKDIR /app
RUN mkdir -p /app/db

COPY resources/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8765 8000

CMD ["supervisord"]

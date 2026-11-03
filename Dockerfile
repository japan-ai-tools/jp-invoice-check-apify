# Standard library only: no pip install, no network at run time except Apify's own charge API.
FROM python:3.12-slim
WORKDIR /app
COPY jpinvoice ./jpinvoice
COPY LICENSE ./
ENV PYTHONUNBUFFERED=1
RUN useradd --create-home app
USER app
# Apify sets ACTOR_WEB_SERVER_PORT; the server then listens on 0.0.0.0 and answers the readiness probe on GET /.
CMD ["python", "-m", "jpinvoice.http_server"]

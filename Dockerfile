FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY etl ./etl
RUN pip install --no-cache-dir .

VOLUME ["/app/data", "/app/site"]
ENTRYPOINT ["python", "-m", "etl.cli"]
CMD ["run"]

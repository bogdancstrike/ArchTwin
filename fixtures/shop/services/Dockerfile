FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && opentelemetry-bootstrap -a requirements | grep -vE "aws|botocore|boto" | pip install --no-cache-dir -r /dev/stdin || true
COPY *.py ./
RUN useradd --uid 10001 --no-create-home shop
USER shop

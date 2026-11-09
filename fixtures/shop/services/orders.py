"""shop-orders: persists orders in PostgreSQL and publishes `orders.created` to Kafka."""
import json
import os

import psycopg
from confluent_kafka import Producer
from fastapi import FastAPI
from opentelemetry.instrumentation.confluent_kafka import ConfluentKafkaInstrumentor

DATABASE_URL = os.environ["DATABASE_URL"]
producer = ConfluentKafkaInstrumentor().instrument_producer(Producer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP"], "client.id": "shop-orders"}))
app = FastAPI(title="shop-orders")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/orders")
def create_order(body: dict):
    with psycopg.connect(DATABASE_URL) as conn:
        oid = conn.execute("INSERT INTO orders (customer_id, sku, qty, total_cents) VALUES (%s, %s, %s, %s) RETURNING id",
                           (body.get("customer_id", 1), body["sku"], body.get("qty", 1), 1999 * body.get("qty", 1))).fetchone()[0]
    producer.produce("orders.created", key=str(oid), value=json.dumps({"order_id": oid, "sku": body["sku"]}))
    producer.flush(5)
    return {"id": oid}


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute("SELECT id, sku, qty, total_cents FROM orders WHERE id = %s", (order_id,)).fetchone()
    return dict(zip(("id", "sku", "qty", "total_cents"), row)) if row else {}

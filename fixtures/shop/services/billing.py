"""shop-billing: consumes `orders.created` (consumer group `billing`)."""
import json
import os
import time

from confluent_kafka import Consumer
from opentelemetry.instrumentation.confluent_kafka import ConfluentKafkaInstrumentor

consumer = ConfluentKafkaInstrumentor().instrument_consumer(Consumer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP"], "group.id": "billing", "auto.offset.reset": "earliest",
                     "client.id": "shop-billing"}))
consumer.subscribe(["orders.created"])

while True:
    msg = consumer.poll(1.0)
    if msg is None or msg.error():
        continue
    event = json.loads(msg.value())
    print("invoiced order", event.get("order_id"), flush=True)
    time.sleep(0.4)       # slower than the producer on purpose: the fixture shows consumer lag

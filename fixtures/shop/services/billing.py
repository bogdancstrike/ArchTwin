"""shop-billing: consumes `orders.created` (consumer group `billing`)."""
import json
import os
import time

from confluent_kafka import Consumer
from opentelemetry import propagate, trace

consumer = Consumer({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP"], "group.id": "billing", "auto.offset.reset": "earliest",
                     "client.id": "shop-billing"})
tracer = trace.get_tracer("shop-billing")
consumer.subscribe(["orders.created"])

while True:
    msg = consumer.poll(1.0)
    if msg is None or msg.error():
        continue
    ctx = propagate.extract({k: v.decode() for k, v in (msg.headers() or [])})
    with tracer.start_as_current_span("orders.created process", context=ctx, kind=trace.SpanKind.CONSUMER,
                                      attributes={"messaging.system": "kafka", "messaging.destination.name": "orders.created",
                                                  "messaging.consumer.group.name": "billing"}):
        event = json.loads(msg.value())
        print("invoiced order", event.get("order_id"), flush=True)
    time.sleep(0.1)       # some processing time: small, non-zero lag shows up between polls

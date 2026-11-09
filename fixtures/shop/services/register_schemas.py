"""Registers the Avro schema for `orders.created` (TopicNameStrategy subject `orders.created-value`)."""
import json
import os
import time

import httpx

URL = os.environ["SCHEMA_REGISTRY_URL"]
SCHEMA = {"type": "record", "name": "OrderCreated", "namespace": "shop.orders",
          "fields": [{"name": "order_id", "type": "long"}, {"name": "sku", "type": "string"}]}
for _ in range(30):
    try:
        r = httpx.post(f"{URL}/subjects/orders.created-value/versions", json={"schema": json.dumps(SCHEMA)},
                       headers={"Content-Type": "application/vnd.schemaregistry.v1+json"}, timeout=5)
        print(r.status_code, r.text)
        break
    except httpx.HTTPError:
        time.sleep(2)

"""shop-loadgen: steady synthetic traffic so the OTel service graph has edges."""
import os
import random
import time

import httpx

WEB = os.environ["WEB_URL"]
time.sleep(8)
while True:
    try:
        sku = random.choice(["sku-1", "sku-2", "sku-3"])
        httpx.get(f"{WEB}/api/products/{sku}", timeout=5)
        if random.random() < 0.6:
            httpx.post(f"{WEB}/api/checkout", json={"sku": sku, "qty": 1, "customer_id": random.choice([1, 2])}, timeout=5)
    except httpx.HTTPError:
        pass
    time.sleep(1.0)

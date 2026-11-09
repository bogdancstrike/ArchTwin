"""shop-web: storefront API. Calls shop-orders and shop-inventory over HTTP."""
import os

import httpx
from fastapi import FastAPI

ORDERS_URL = os.environ["ORDERS_URL"]
INVENTORY_URL = os.environ["INVENTORY_URL"]
app = FastAPI(title="shop-web")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/products/{sku}")
def product(sku: str):
    stock = httpx.get(f"{INVENTORY_URL}/stock/{sku}", timeout=5).json()
    return {"sku": sku, "stock": stock}


@app.post("/api/checkout")
def checkout(body: dict):
    stock = httpx.get(f"{INVENTORY_URL}/stock/{body['sku']}", timeout=5).json()
    if stock["available"] < body.get("qty", 1):
        return {"ok": False, "reason": "out of stock"}
    order = httpx.post(f"{ORDERS_URL}/orders", json=body, timeout=5).json()
    return {"ok": True, "order": order}

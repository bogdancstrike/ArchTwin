"""shop-inventory: stock levels from MySQL."""
import os
from urllib.parse import urlparse

import pymysql
from fastapi import FastAPI

u = urlparse(os.environ["DATABASE_URL"])
app = FastAPI(title="shop-inventory")


def db():
    return pymysql.connect(host=u.hostname, port=u.port or 3306, user=u.username, password=u.password, database=u.path.lstrip("/"))


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/stock/{sku}")
def stock(sku: str):
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(qty), 0) FROM stock WHERE sku = %s", (sku,))
            return {"sku": sku, "available": int(cur.fetchone()[0])}
    finally:
        conn.close()

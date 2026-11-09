from fastapi import FastAPI

from app.api import orders

app = FastAPI()
app.include_router(orders.router)


@app.get("/health")
async def health():
    return {"ok": True}

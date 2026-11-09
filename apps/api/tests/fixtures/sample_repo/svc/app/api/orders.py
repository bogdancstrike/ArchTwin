from fastapi import APIRouter

from ..db import session

router = APIRouter(prefix="/orders")


@router.get("/{order_id}")
async def get_order(order_id: str):
    return session(order_id)


@router.post("")
async def create_order():
    return {}

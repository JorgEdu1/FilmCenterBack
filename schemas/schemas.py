from pydantic import BaseModel
from datetime import date
from typing import Optional

class StreamingCreate(BaseModel):
    user_id: int
    name: str
    price: float
    billing_date: date

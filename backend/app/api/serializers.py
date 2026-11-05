"""ORM → dict. 개인정보는 기본 마스킹."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.models import Order
from app.security import decrypt_pii, mask_address, mask_name, mask_phone


def to_dict(obj, exclude: set[str] | None = None) -> dict:
    out = {}
    for col in obj.__table__.columns:
        if exclude and col.name in exclude:
            continue
        v = getattr(obj, col.name)
        if isinstance(v, Decimal):
            v = str(v)
        elif isinstance(v, Enum):
            v = v.value
        elif isinstance(v, datetime):
            v = v.isoformat()
        out[col.name] = v
    return out


PII_COLS = {"buyer_name_enc", "buyer_phone_enc", "address_enc"}


def order_dict(o: Order, reveal: bool = False) -> dict:
    d = to_dict(o, exclude=PII_COLS)
    name, phone, addr = decrypt_pii(o.buyer_name_enc), decrypt_pii(o.buyer_phone_enc), decrypt_pii(o.address_enc)
    d["buyer"] = ({"name": name, "phone": phone, "address": addr} if reveal else
                  {"name": mask_name(name), "phone": mask_phone(phone), "address": mask_address(addr)})
    d["product_title"] = o.product.title if o.product else None
    d["supplier_code"] = o.supplier.code if o.supplier else None
    return d

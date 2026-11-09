"""승인된 CSV/Excel 상품 데이터 피드 Adapter.

공급사로부터 정식으로 제공받은 파일만 사용한다. config:
  path: 파일 경로 (.csv / .xlsx)
  column_map: {표준필드: 파일컬럼명} (선택)
발주 API 가 없으므로 주문은 관리자 승인(수동 발주) 대기로 전환된다.
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.adapters.base import AdapterError, StockInfo, SupplierAdapter, SupplierItem

DEFAULT_COLUMNS = {
    "sku": "sku", "name": "name", "supply_price": "supply_price", "shipping_fee": "shipping_fee",
    "stock": "stock", "brand": "brand", "category": "category", "images": "images", "options": "options",
    "manufacturer": "manufacturer", "origin": "origin", "material": "material", "retail_price": "retail_price",
    "description": "description",
}


def _num(v, default="0") -> Decimal:
    try:
        return Decimal(str(v).replace(",", "").strip() or default)
    except InvalidOperation:
        return Decimal(default)


class CsvSupplierAdapter(SupplierAdapter):
    is_live = False
    supports_purchase = False

    def _rows(self) -> list[dict]:
        path = Path(self.config.get("path", ""))
        if not path.is_file():
            raise AdapterError(f"피드 파일 없음: {path}")
        if path.suffix.lower() in (".xlsx", ".xlsm"):
            from openpyxl import load_workbook

            ws = load_workbook(path, read_only=True, data_only=True).active
            rows = list(ws.iter_rows(values_only=True))
            header = [str(h).strip() if h is not None else "" for h in rows[0]]
            return [dict(zip(header, r)) for r in rows[1:] if any(c is not None for c in r)]
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def fetch_products(self) -> list[SupplierItem]:
        cols = {**DEFAULT_COLUMNS, **(self.config.get("column_map") or {})}
        g = lambda r, k: r.get(cols[k])  # noqa: E731
        items = []
        for r in self._rows():
            sku = str(g(r, "sku") or "").strip()
            if not sku:
                continue
            images = [u.strip() for u in str(g(r, "images") or "").split("|") if u.strip()]
            raw_opts = g(r, "options")
            options = []
            if raw_opts:
                try:
                    options = json.loads(raw_opts)
                except (TypeError, ValueError):
                    options = [{"name": o.strip(), "sku": f"{sku}-{i}", "stock": None, "extra_price": 0}
                               for i, o in enumerate(str(raw_opts).split("|")) if o.strip()]
            attrs = {k: g(r, k) for k in ("manufacturer", "origin", "material") if g(r, k)}
            if g(r, "retail_price"):
                attrs["retail_price"] = float(_num(g(r, "retail_price")))
            items.append(SupplierItem(
                sku=sku, name=str(g(r, "name") or "").strip(), supply_price=_num(g(r, "supply_price")),
                shipping_fee=_num(g(r, "shipping_fee")), stock=int(_num(g(r, "stock"))),
                brand=(str(g(r, "brand")).strip() if g(r, "brand") else None),
                category_hint=g(r, "category"), images=images, options=options, attributes=attrs,
                description=g(r, "description"),
            ))
        return items

    def get_stock(self, sku: str) -> StockInfo:
        for item in self.fetch_products():
            if item.sku == sku:
                return StockInfo(sku, item.stock, item.supply_price, item.stock > 0)
        return StockInfo(sku, 0, Decimal(0), False)

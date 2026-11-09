import pytest
from openpyxl import Workbook

from app.adapters.base import PurchaseNotSupported
from app.adapters.csv_supplier import CsvSupplierAdapter


def test_csv_feed(tmp_path):
    f = tmp_path / "feed.csv"
    f.write_text("sku,name,supply_price,shipping_fee,stock,brand,images,options,origin,manufacturer\n"
                 "C1,수납함 대형,\"5,500\",3000,10,,https://a/1.jpg|https://a/2.jpg,블랙|화이트,중국,(주)가나\n"
                 ",빈 코드 행,1,1,1,,,,,\n", encoding="utf-8")
    a = CsvSupplierAdapter("CSV", {"path": str(f)})
    items = a.fetch_products()
    assert len(items) == 1
    it = items[0]
    assert it.supply_price == 5500 and it.stock == 10 and len(it.images) == 2
    assert [o["name"] for o in it.options] == ["블랙", "화이트"]
    assert it.attributes == {"manufacturer": "(주)가나", "origin": "중국"}
    assert a.get_stock("C1").available and not a.get_stock("NOPE").available
    with pytest.raises(PurchaseNotSupported):
        a.place_order(None)


def test_xlsx_feed_with_column_map(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["상품코드", "상품명", "공급가", "배송비", "재고"])
    ws.append(["X1", "텀블러", 7000, 3000, 0])
    p = tmp_path / "feed.xlsx"
    wb.save(p)
    a = CsvSupplierAdapter("X", {"path": str(p), "column_map": {"sku": "상품코드", "name": "상품명",
                                                                 "supply_price": "공급가", "shipping_fee": "배송비", "stock": "재고"}})
    [it] = a.fetch_products()
    assert it.sku == "X1" and it.stock == 0 and it.supply_price == 7000

from app.adapters.base import SupplierAdapter
from app.adapters.csv_supplier import CsvSupplierAdapter
from app.adapters.mock_supplier import MockSupplierAdapter
from app.models import Supplier

ADAPTERS: dict[str, type[SupplierAdapter]] = {
    "mock": MockSupplierAdapter,
    "csv": CsvSupplierAdapter,
    # "acme_api": AcmeApiAdapter,  ← 실제 공급사 API 명세 확보 후 추가
}


def get_adapter(supplier: Supplier) -> SupplierAdapter:
    cls = ADAPTERS.get(supplier.adapter_type)
    if cls is None:
        raise ValueError(f"지원하지 않는 adapter_type: {supplier.adapter_type}")
    # config 는 복사본을 넘긴다 (Mock 의 시도 횟수 기록은 호출자가 저장 여부 결정)
    return cls(supplier.code, dict(supplier.config or {}))

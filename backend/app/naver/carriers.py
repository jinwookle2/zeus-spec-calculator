"""택배사 코드 매핑: 공급사 코드/이름 → 네이버 deliveryCompanyCode.

네이버 코드값(CJGLS, HANJIN, LOTTE, EPOST, LOGEN 등)은 2차 출처 기반이므로
운영 전 네이버 커머스API '택배사 코드' 문서로 재확인하고 설정(carrier_code_map)에서 수정한다.
"""
DEFAULT_CARRIER_MAP = {
    "CJ": "CJGLS", "CJ대한통운": "CJGLS", "대한통운": "CJGLS", "CJGLS": "CJGLS",
    "한진": "HANJIN", "한진택배": "HANJIN", "HANJIN": "HANJIN",
    "롯데": "LOTTE", "롯데택배": "LOTTE", "LOTTE": "LOTTE",
    "우체국": "EPOST", "우체국택배": "EPOST", "EPOST": "EPOST",
    "로젠": "LOGEN", "로젠택배": "LOGEN", "LOGEN": "LOGEN",
}


def map_carrier(code: str | None, overrides: dict | None = None) -> str | None:
    if not code:
        return None
    table = {**DEFAULT_CARRIER_MAP, **(overrides or {})}
    key = code.strip()
    return table.get(key) or table.get(key.upper())

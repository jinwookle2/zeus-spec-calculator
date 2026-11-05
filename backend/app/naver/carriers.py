"""택배사 코드 매핑: 공급사 코드/이름 → 네이버 deliveryCompanyCode.

출처: 네이버 커머스API 공식 문서 v2.91.0 (2026-10-28) '발송 처리' deliveryCompanyCode 표.
주의: 롯데택배 = HYUNDAI, 로젠택배 = KGB (이름과 코드가 다름).
여기 없는 택배사는 관리자 설정 carrier_code_map 에 {공급사값: 네이버코드} 로 추가한다.
"""
_OFFICIAL = {
    "CJGLS": ["CJ", "CJ대한통운", "대한통운"],
    "HYUNDAI": ["롯데", "롯데택배", "LOTTE"],
    "HANJIN": ["한진", "한진택배"],
    "KGB": ["로젠", "로젠택배", "LOGEN"],
    "EPOST": ["우체국", "우체국택배"],
    "KDEXP": ["경동", "경동택배"],
    "DAESIN": ["대신", "대신택배"],
    "ILYANG": ["일양", "일양로지스"],
    "HDEXP": ["합동", "합동택배"],
    "CHUNIL": ["천일", "천일택배"],
    "KUNYOUNG": ["건영", "건영택배"],
    "CUPARCEL": ["CU편의점택배", "CU택배"],
    "CVSNET": ["GS편의점택배", "GSPostbox택배", "GS택배"],
    "NONGHYUP": ["농협택배"],
    "SLX": ["SLX택배"],
    "CH1": ["기타택배"],
}
DEFAULT_CARRIER_MAP: dict[str, str] = {}
for code, aliases in _OFFICIAL.items():
    DEFAULT_CARRIER_MAP[code] = code
    for a in aliases:
        DEFAULT_CARRIER_MAP[a] = code


def map_carrier(code: str | None, overrides: dict | None = None) -> str | None:
    if not code:
        return None
    table = {**DEFAULT_CARRIER_MAP, **(overrides or {})}
    key = code.strip()
    return table.get(key) or table.get(key.upper()) or table.get(key.replace(" ", ""))

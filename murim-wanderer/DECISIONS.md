# 기술 결정 기록 (DECISIONS)

## D-001 엔진: Godot 4.4.1 stable (표준판, GDScript)
- 개발 환경에 Godot 이 없어 공식 GitHub 릴리스 바이너리(4.4.1-stable)로 검증했다.
- 프로젝트는 4.4 기능만 사용하므로 4.4.x / 4.5.x 에디터에서 열 수 있다.

## D-002 렌더러: Compatibility (OpenGL ES 3 / WebGL2)
- 2D 픽셀 게임에는 Forward+/Mobile 렌더러의 이점이 거의 없고, Compatibility 가 구형 안드로이드 기기 호환성이 가장 넓다.

## D-003 해상도: 내부 640×360, stretch=viewport, aspect=expand
- 640×360 은 1280×720 / 1920×1080 / 2560×1440 에 정수 배율로 맞는다 → 픽셀이 깨지지 않음.
- `expand` 로 19.5:9 등 긴 휴대폰 화면에서는 좌우로, 4:3 태블릿에서는 위아래로 보이는 영역이 늘어난다(검은 띠 없음).
  UI 는 앵커 기반이라 가장자리에 붙어 따라간다.
- 텍스처 필터: Nearest (흐림 방지), 2D 변환/정점 픽셀 스냅 켬.
- 노치·펀치홀: `SafeArea` 가 모바일에서 안전 영역 여백을 계산해 HUD·터치 버튼에 적용.

## D-004 맵: 문자 지도(JSON) → 실행 시 TileMapLayer 생성
- `data/maps/*.json` 의 `tiles` 문자열을 `MapBuilder` 가 TileMapLayer(4.3+ 권장 노드)로 변환한다.
- 타일셋(TileSet)과 충돌 폴리곤도 `data/maps/tiles.json` 의 `solid` 값으로 코드에서 만든다.
- 이유: 비개발자도 텍스트 편집기로 맵을 고칠 수 있고, 자동 테스트로 맵 무결성(크기, 범례, NPC 위치)을 검증할 수 있다.
- 단점: 에디터에서 맵이 미리 보이지 않는다 → 추후 큰 맵은 Godot 에디터 TileMap 편집 방식으로 전환 검토 (TODO).

## D-005 데이터 주도 설계
- 능력치, 성장, 경험치 곡선, 적 행동 패턴, 무술, 아이템, 대사, 임무, 전투 공식 계수는 전부 `data/*.json`.
- 대사는 조건부 variant(`if_flag`, `if_not_flag`, `if_quest`)와 효과(`set_flags`, `give_items`, `quest`, `heal`)를 지원.
- 주의: 내보내기(export) 시 `data/*`, `*.json` 을 "리소스 외 파일 포함" 필터에 추가해야 한다 (TODO 에 기록).

## D-006 전투: 규칙(BattleLogic)과 연출(battle_scene) 분리
- `BattleLogic` 은 화면과 무관한 RefCounted 클래스 → 시드 고정 난수로 단위 테스트.
- 피해 공식: `max(최소피해, (공격×위력 − 방어×0.5) × 난수[0.85~1.15]) × 치명타(8%, ×1.5) × 기합(×1.8) × 방어(×0.5)`, 최종 최소 1.
- 턴 순서: 플레이어 행동 → 적 행동 (민첩성은 현재 도주 확률에만 사용; 속도 기반 턴 순서는 TODO).

## D-007 저장: JSON + 버전 + SHA-256 체크섬 + 백업 + 원자적 교체
- `user://savegame.json` (모바일 앱 전용 저장소). 임시 파일에 쓴 뒤 rename → 저장 중 종료돼도 기존 파일 보존.
- 저장할 때마다 직전 저장본을 `.bak` 으로 보관. 본 파일이 손상/변조되면 백업으로 자동 복구, 둘 다 실패하면 안전하게 거부.
- 미래 버전 파일은 거부, 과거 버전은 `SaveManager.migrate()` 에서 변환.
- 저장 슬롯은 1개 (프로토타입). 설정은 별도 `user://settings.cfg`.

## D-008 입력: 액션 이름으로 통일
- 키보드·패드·터치 버튼 모두 `move_*`, `interact`, `cancel`, `menu` 액션을 발생시킨다.
- 키 매핑은 `scripts/core/input_setup.gd` 에서 코드로 등록 (project.godot 직렬화보다 읽기 쉬움).
- 터치: `TouchScreenButton` (멀티터치 지원, 방향키는 passby_press 로 손가락 미끄러짐 허용).

## D-009 폰트: Galmuri11 (OFL)
- 한글 픽셀 폰트. 기본 Godot 폰트는 모바일에서 한글이 보장되지 않아 반드시 내장 폰트가 필요.
- 12px 배수 크기에서 안티앨리어싱 끄고 사용 → 선명한 픽셀 글자.

## D-010 그래픽: 코드 생성 임시 픽셀아트
- 이미지 생성 도구가 없어 `tools/gen_art.py`(Pillow)로 독창적 임시 그래픽을 생성.
- 32×32 타일/캐릭터, 4방향×3프레임 걷기 시트. 자동 외곽선 처리로 16비트 RPG 느낌.

## D-011 프로젝트 위치
- 작업 저장소(`zeus-spec-calculator`)의 기존 파일은 건드리지 않고 하위 폴더 `murim-wanderer/` 에 독립 Godot 프로젝트로 생성.
- 추후 별도 저장소로 분리 권장 (TODO).

# 무림유랑기: 천하제일 허당전 (Murim Wanderer)

2D 픽셀아트 코믹 무협 RPG — iOS / Android 목표, Godot 4 + GDScript.

> 천하제일 고수를 꿈꾸는 무명 무술가 **도윤**이 낡은 비급 조각의 비밀을 찾아 떠나는 유쾌한 모험.

## 바로 실행하기

1. **Godot 4.4 이상(표준판, .NET 아님)** 을 설치합니다 → https://godotengine.org/download
   - 개발·검증 버전: **Godot 4.4.1 stable**
2. Godot 실행 → **가져오기(Import)** → 이 폴더의 `project.godot` 선택 → **가져오기 및 편집**
3. 에디터 우측 상단 **▶ (F5)** 를 누르면 시작 화면부터 실행됩니다.

명령줄로 실행하려면:

```bash
godot --path murim-wanderer            # 게임 실행
godot --path murim-wanderer -e         # 에디터 열기
```

## 조작법

| 동작 | 키보드 | 모바일 터치 | 게임패드 |
|---|---|---|---|
| 이동 (4방향) | 방향키 / WASD | 왼쪽 아래 방향키 | 십자키 |
| 대화·조사·확인 | Z / Space / Enter | **확인** 버튼 / 대화창 탭 | A |
| 메뉴 | Esc / C / Tab | **메뉴** 버튼 / 우측 상단 「메뉴」 | Start |
| 취소·뒤로 | X / Backspace | 「뒤로」 버튼 | B |

데스크톱에서는 마우스로 터치 버튼을 눌러 볼 수 있습니다 (설정 → 터치 버튼: 켜기).

## 프로토타입에서 할 수 있는 것

- 시작 화면: 새 게임 / 이어하기 / 설정 / 종료(데스크톱)
- 청풍마을(30×20 타일) 탐험 — 집 3채, 도장 청풍관, 만복상회, 우물, 연못, NPC 3명
- NPC 대화 (사범 백운, 주민 순이, 상인 만복) + 숨겨진 조사 이벤트 (연못, 항아리…)
- 남쪽 출구 → 청풍 수련장 → **초급 산적 덕팔** 매복 전투, 허수아비 수련 전투(반복 가능)
- 턴제 전투: 공격 / 무술(기본권·연속권·기합) / 방어 / 아이템 / 도주, 레벨업
- 필드 메뉴: 상태창, 아이템 사용, 저장, 설정
- 저장/불러오기 (버전·체크섬·백업 포함)

## 폴더 구조

```
murim-wanderer/
├── project.godot           # 프로젝트 설정 (640x360, 픽셀 필터, 오토로드)
├── scenes/                 # .tscn 장면
│   ├── main/               #   시작 화면
│   ├── world/              #   필드 (맵 데이터로 구성)
│   ├── player/  npc/       #   캐릭터
│   ├── battle/             #   전투
│   └── ui/                 #   HUD, 대화창, 터치 버튼, 메뉴
├── scripts/
│   ├── core/               #   GameState, DataDB, Settings, SceneRouter 등 싱글턴
│   ├── world/  player/ npc/
│   ├── battle/             #   battle_logic.gd(규칙) + battle_scene.gd(연출)
│   ├── save/               #   SaveManager
│   └── ui/
├── data/                   # ★ 기획 수치/대사 — 코드 수정 없이 편집 가능
│   ├── characters/player.json   능력치, 성장치, 경험치 곡선
│   ├── enemies/enemies.json     적 능력치, 행동 패턴, 대사
│   ├── skills/skills.json       무술 (MP, 위력, 타수)
│   ├── items/items.json         아이템
│   ├── dialogue/cheongpung.json NPC 대사 (조건/보상 포함)
│   ├── quests/quests.json       임무
│   ├── battle/battle_config.json 피해 공식 계수, 도주 확률
│   └── maps/                    맵(문자 지도), 타일 범례
├── assets/                 # 그래픽(전부 자체 제작), 폰트
├── tools/gen_art.py        # 임시 픽셀아트 생성기 (Python + Pillow)
├── tests/                  # 자동 테스트
└── docs/                   # 개발 문서
```

## 데이터 수정 예시

- **대사 바꾸기**: `data/dialogue/cheongpung.json` 의 문장을 고치고 실행하면 끝.
- **맵 고치기**: `data/maps/cheongpung.json` 의 `tiles` 문자열에서 글자를 바꿉니다.
  (`.` 풀, `#` 길, `T` 나무, `=` 울타리, `~` 물, … 전체 목록은 `data/maps/tiles.json`)
- **밸런스**: `data/enemies/enemies.json`, `data/battle/battle_config.json`.

## 테스트

```bash
# 전체 자동 테스트 (데이터 검증 + 전투 로직 + 저장 + 실제 플레이 시나리오)
godot --headless --path murim-wanderer res://tests/test_runner.tscn

# 화면 캡처 포함 (디스플레이 필요, 리눅스 서버는 xvfb-run 사용)
godot --path murim-wanderer --rendering-driver opengl3 res://tests/test_runner.tscn -- --shots=/tmp/shots
```

## 그래픽 다시 만들기

```bash
pip install pillow
python3 tools/gen_art.py
```

## 라이선스 / 에셋 출처

`docs/ASSETS.md` 참조. 외부 에셋은 Galmuri 폰트(SIL OFL 1.1, 상업적 이용 가능) 하나뿐입니다.

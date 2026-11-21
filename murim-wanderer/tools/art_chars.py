"""무림유랑기 캐릭터 아트 v4 — 개성 있는 SD 비율 + 표정 + 전투 자세.

- 필드: 32x48 셀, 4방향 x 3프레임 (gen_art.char_sheet 와 같은 배치)
- 초상화: 32x32 (대화창에서 2배), 표정 normal/happy/angry/surprised/sweat
- 전투 자세: 48x48 셀(3배 확대해 144x144), 관절 좌표로 포즈를 잡는다

기존 게임의 캐릭터를 모사하지 않는다. 큰 머리·과장된 표정·뚜렷한 실루엣이라는
장르적 표현만 참고한 이 프로젝트의 독창적 디자인이다.
"""
from __future__ import annotations

import math
from PIL import Image

from gen_art import (new, rect, px, circle, ellipse, outline, scale, save, shade,
                     CLEAR, OUT, EYE)

W, H = 32, 48
WHITE = (248, 244, 232, 255)
BLUSH = (232, 140, 120, 255)
TOOTH = (250, 248, 240, 255)
SWEAT = (150, 200, 240, 255)

# ---------------------------------------------------------------- 캐릭터 정의
CHARS = {
    "doyun": dict(
        skin=(240, 196, 156, 255), hair=(34, 28, 36, 255), hair_style="spiky",
        band=(196, 40, 36, 255), brows="bold", mouth="grin", bandage=True,
        top=(236, 230, 214, 255), vest=(48, 62, 104, 255), sash=(196, 40, 36, 255),
        sleeve=(236, 230, 214, 255), glove=(196, 40, 36, 255),
        pants=(64, 62, 72, 255), shoes=(36, 30, 32, 255), wraps=(236, 230, 214, 255),
    ),
    "master": dict(
        skin=(236, 196, 160, 255), hair=(244, 244, 240, 255), hair_style="bald",
        brows="drape", mouth="beard", beard=(244, 244, 240, 255),
        top=(150, 140, 168, 255), vest=None, sash=(80, 64, 60, 255),
        sleeve=(150, 140, 168, 255), glove=None, robe=True,
        pants=(110, 100, 126, 255), shoes=(60, 46, 40, 255), staff=True,
    ),
    "villager": dict(
        skin=(246, 206, 172, 255), hair=(52, 34, 30, 255), hair_style="twinbuns",
        ribbon=(214, 60, 70, 255), brows="soft", mouth="smile", lashes=True,
        top=(248, 214, 110, 255), vest=None, sash=(214, 60, 70, 255),
        sleeve=(248, 214, 110, 255), glove=None, skirt=(64, 80, 140, 255),
        pants=(64, 80, 140, 255), shoes=(240, 236, 228, 255),
    ),
    "merchant": dict(
        skin=(240, 194, 150, 255), hair=(40, 32, 30, 255), hair_style="gat",
        hat=(28, 26, 30, 255), brows="thin", mouth="mustache", eyes="squint",
        top=(196, 150, 70, 255), vest=None, sash=(60, 100, 150, 255),
        sleeve=(196, 150, 70, 255), glove=None, wide=4, belly=True, abacus=True,
        pants=(120, 90, 60, 255), shoes=(60, 44, 36, 255),
    ),
    "bandit": dict(
        skin=(214, 160, 120, 255), hair=(30, 26, 26, 255), hair_style="baldknot",
        brows="unibrow", mouth="snaggle", eyepatch=True, stubble=True, scar=True,
        top=(214, 160, 120, 255), vest=(120, 84, 52, 255), fur=(186, 160, 120, 255),
        sash=(60, 50, 44, 255), sleeve=None, glove=(80, 60, 44, 255), wide=3,
        pants=(84, 74, 80, 255), shoes=(50, 40, 36, 255),
    ),
}


# ---------------------------------------------------------------- 공용 그리기
def thick_line(img, p0, p1, w, c):
    x0, y0 = p0
    x1, y1 = p1
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(n + 1):
        t = i / max(1, n)
        x = round(x0 + (x1 - x0) * t)
        y = round(y0 + (y1 - y0) * t)
        rect(img, x - w // 2, y - w // 2, x - w // 2 + w - 1, y - w // 2 + w - 1, c)


def round_head(img, x0, y0, x1, y1, c):
    rect(img, x0, y0, x1, y1, c)
    for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        px(img, cx, cy, CLEAR)
        px(img, cx + dx, cy, CLEAR)
        px(img, cx, cy + dy, CLEAR)


# ---------------------------------------------------------------- 얼굴 (정면)
def face_front(img, c, ox, oy, expr="normal"):
    """머리 영역 (ox..ox+15, oy..oy+18) 위에 얼굴을 그린다."""
    lx, rx, ey = ox + 3, ox + 11, oy + 10
    style = c.get("eyes", "big")
    # 눈
    if c.get("brows") == "drape" and expr in ("normal", "sweat", "happy"):
        rect(img, lx, ey + 1, lx + 2, ey + 1, EYE)  # 눈썹에 가려진 실눈
        rect(img, rx, ey + 1, rx + 2, ey + 1, EYE)
    elif expr == "happy" or (style == "squint" and expr != "surprised" and expr != "angry"):
        for x0 in (lx, rx):
            px(img, x0 - 1, ey + 2, EYE)
            rect(img, x0, ey + 1, x0 + 2, ey + 1, EYE)
            px(img, x0 + 3, ey + 2, EYE)
    elif expr == "surprised":
        for x0 in (lx, rx):
            rect(img, x0, ey - 1, x0 + 2, ey + 2, WHITE)
            px(img, x0 + 1, ey + 1, EYE)
    elif expr == "angry":
        for x0 in (lx, rx):
            rect(img, x0, ey + 1, x0 + 2, ey + 2, EYE)
            px(img, x0 + (2 if x0 == lx else 0), ey + 1, WHITE)
    else:
        for x0 in (lx, rx):
            rect(img, x0, ey, x0 + 2, ey + 2, EYE)
            px(img, x0, ey, WHITE)
            if c.get("lashes"):
                px(img, x0 - 1, ey - 1, EYE)
                px(img, x0 + 3, ey - 1, EYE)
    if c.get("eyepatch"):
        rect(img, rx - 1, ey - 1, rx + 3, ey + 2, (30, 24, 26, 255))
        thick_line(img, (ox, ey - 3), (ox + 15, ey - 1), 1, (30, 24, 26, 255))
    # 눈썹
    b = c.get("brows")
    bc = c["hair"] if b != "drape" else c.get("beard", WHITE)
    by = ey - 2 - (1 if expr == "surprised" else 0)
    if b == "bold":
        if expr == "angry":
            thick_line(img, (lx - 1, by - 1), (lx + 2, by + 1), 1, bc)
            thick_line(img, (rx, by + 1), (rx + 3, by - 1), 1, bc)
        else:
            rect(img, lx - 1, by, lx + 2, by, bc)
            rect(img, rx, by, rx + 3, by, bc)
            px(img, lx + 2, by + 1, bc)
            px(img, rx, by + 1, bc)
    elif b == "unibrow":
        rect(img, lx - 1, by, rx + 3, by, bc)
        rect(img, lx + 2, by + 1, rx, by + 1, bc)
    elif b == "drape":
        rect(img, lx - 2, by, lx + 3, by + 1, bc)
        rect(img, rx - 1, by, rx + 4, by + 1, bc)
        rect(img, lx - 3, by + 2, lx - 2, by + 5, bc)  # 축 늘어진 눈썹
        rect(img, rx + 4, by + 2, rx + 5, by + 5, bc)
    elif b == "thin":
        rect(img, lx, by, lx + 2, by, bc)
        rect(img, rx, by, rx + 2, by, bc)
    else:
        rect(img, lx, by, lx + 2, by, shade(bc, 1.2))
        rect(img, rx, by, rx + 2, by, shade(bc, 1.2))
    if expr == "angry" and b != "bold":
        px(img, lx + 2, by + 1, bc)
        px(img, rx, by + 1, bc)
    # 볼
    if expr in ("happy", "normal") and c.get("brows") != "unibrow":
        px(img, lx - 1, ey + 4, BLUSH)
        px(img, rx + 3, ey + 4, BLUSH)
    if c.get("bandage"):
        rect(img, rx + 1, ey + 4, rx + 3, ey + 5, WHITE)
        px(img, rx + 2, ey + 4, (220, 200, 190, 255))
    if c.get("scar"):
        thick_line(img, (lx - 1, ey - 2), (lx + 2, ey + 4), 1, (170, 90, 80, 255))
    if c.get("stubble"):
        for x in range(ox + 3, ox + 13, 2):
            px(img, x, oy + 17, shade(c["skin"], 0.7))
    # 입
    my = oy + 15
    m = c.get("mouth")
    if m == "beard":
        pass
    elif expr == "surprised":
        rect(img, ox + 7, my - 1, ox + 8, my + 1, (120, 40, 40, 255))
    elif expr == "angry":
        rect(img, ox + 5, my, ox + 10, my, TOOTH)
        rect(img, ox + 5, my + 1, ox + 10, my + 1, (120, 40, 40, 255))
    elif expr == "sweat":
        for i, x in enumerate(range(ox + 5, ox + 11)):
            px(img, x, my + (i % 2), (120, 50, 50, 255))
    elif m == "grin" or expr == "happy":
        rect(img, ox + 5, my, ox + 10, my, (120, 40, 40, 255))
        rect(img, ox + 6, my, ox + 9, my, TOOTH)
        px(img, ox + 5, my - 1, (120, 40, 40, 255))
        px(img, ox + 10, my - 1, (120, 40, 40, 255))
    elif m == "snaggle":
        rect(img, ox + 5, my, ox + 10, my, (110, 40, 40, 255))
        px(img, ox + 6, my, TOOTH)
        px(img, ox + 9, my, TOOTH)
        px(img, ox + 6, my - 1, TOOTH)
    elif m == "smile":
        rect(img, ox + 6, my, ox + 9, my, (170, 60, 60, 255))
        px(img, ox + 5, my - 1, (170, 60, 60, 255))
        px(img, ox + 10, my - 1, (170, 60, 60, 255))
    else:
        rect(img, ox + 6, my, ox + 9, my, (150, 70, 60, 255))
    if m == "mustache":
        rect(img, ox + 4, my - 2, ox + 11, my - 2, c["hair"])
        px(img, ox + 3, my - 1, c["hair"])
        px(img, ox + 12, my - 1, c["hair"])
        px(img, ox + 2, my, c["hair"])
        px(img, ox + 13, my, c["hair"])
    if expr == "sweat":
        rect(img, ox + 15, oy + 5, ox + 16, oy + 8, SWEAT)
        px(img, ox + 15, oy + 9, SWEAT)
        px(img, ox + 16, oy + 4, WHITE)


def hair_front(img, c, ox, oy, frame=0, back=False):
    hc = c["hair"]
    hl = shade(hc, 1.5) if hc[0] < 128 else shade(hc, 0.9)
    s = c["hair_style"]
    if s == "spiky":
        rect(img, ox, oy, ox + 15, oy + 5, hc)
        for i, x in enumerate((ox - 1, ox + 3, ox + 7, ox + 11, ox + 15)):
            h = 3 + (i % 2)
            thick_line(img, (x + 1, oy), (x + (1 if i < 2 else 2), oy - h), 2, hc)
        thick_line(img, (ox + 8, oy), (ox + 9, oy - 6), 1, hc)  # 삐친 머리
        if back:
            rect(img, ox, oy, ox + 15, oy + 16, hc)
        else:
            for x in (ox + 2, ox + 6, ox + 10, ox + 13):  # 앞머리
                rect(img, x, oy + 5, x + 1, oy + 7, hc)
            rect(img, ox, oy + 5, ox, oy + 10, hc)
            rect(img, ox + 15, oy + 5, ox + 15, oy + 10, hc)
        rect(img, ox + 3, oy - 1, ox + 5, oy, hl)
    elif s == "bald":
        rect(img, ox + 3, oy, ox + 5, oy + 1, (255, 236, 210, 255))
        rect(img, ox, oy + 7, ox + 1, oy + 11, hc)
        rect(img, ox + 14, oy + 7, ox + 15, oy + 11, hc)
        if back:
            rect(img, ox, oy + 8, ox + 15, oy + 12, hc)
    elif s == "baldknot":
        rect(img, ox + 6, oy - 4, ox + 9, oy - 1, hc)
        rect(img, ox + 6, oy - 1, ox + 9, oy - 1, (150, 40, 40, 255))
        rect(img, ox + 3, oy + 1, ox + 5, oy + 2, shade(c["skin"], 1.12))
    elif s == "twinbuns":
        rect(img, ox, oy, ox + 15, oy + 4, hc)
        for bx in (ox - 3, ox + 13):
            circle(img, bx + 3, oy - 1, 3, hc)
            rect(img, bx + 1, oy + 2, bx + 5, oy + 2, c["ribbon"])
        if back:
            rect(img, ox, oy, ox + 15, oy + 15, hc)
        else:
            rect(img, ox, oy + 4, ox + 1, oy + 12, hc)
            rect(img, ox + 14, oy + 4, ox + 15, oy + 12, hc)
            rect(img, ox + 2, oy + 4, ox + 13, oy + 5, hc)
        rect(img, ox + 3, oy, ox + 6, oy, hl)
    elif s == "gat":
        rect(img, ox, oy + 2, ox + 15, oy + 6, hc)
        if back:
            rect(img, ox, oy + 2, ox + 15, oy + 14, hc)
        hat = c["hat"]
        rect(img, ox + 4, oy - 5, ox + 11, oy + 1, hat)
        rect(img, ox + 5, oy - 4, ox + 10, oy - 3, shade(hat, 2.2))
        rect(img, ox - 4, oy + 2, ox + 19, oy + 2, hat)
        rect(img, ox - 3, oy + 1, ox + 18, oy + 1, shade(hat, 1.6))
        if not back:
            px(img, ox + 1, oy + 12, hat)
            px(img, ox + 14, oy + 12, hat)
    if c.get("band") and s == "spiky":
        rect(img, ox, oy + 6 if not back else oy + 6, ox + 15, oy + 7, c["band"])
        if back:
            sw = (0, 1, -1)[frame]
            thick_line(img, (ox + 7, oy + 8), (ox + 5 + sw, oy + 16), 2, c["band"])
            thick_line(img, (ox + 9, oy + 8), (ox + 11 - sw, oy + 17), 2, c["band"])


# ---------------------------------------------------------------- 필드: 정면/뒷면
def draw_front(c, frame=0, back=False, expr="normal"):
    img = new(W, H)
    bob = -1 if frame in (1, 2) else 0
    w = c.get("wide", 0)
    l_off = -2 if frame == 1 else 0
    r_off = -2 if frame == 2 else 0
    # 다리 / 치마 / 긴 옷
    if c.get("skirt"):
        sk = c["skirt"]
        for y in range(30, 45):
            spread = (y - 30) // 4
            rect(img, 10 - spread, y, 21 + spread, y, sk)
        rect(img, 18, 32, 21 + 3, 44, shade(sk, 0.82))
        rect(img, 7, 45, 24, 45, shade(sk, 0.7))
        rect(img, 11, 46, 14, 46, c["shoes"])
        rect(img, 17, 46, 20, 46, c["shoes"])
    elif c.get("robe"):
        rect(img, 8, 30, 23, 44, c["top"])
        rect(img, 20, 30, 23, 44, shade(c["top"], 0.8))
        rect(img, 8, 44, 23, 44, shade(c["top"], 0.65))
        rect(img, 15, 36, 16, 44, shade(c["top"], 0.75))
        rect(img, 10, 45 + (0 if frame != 1 else -1), 14, 46, c["shoes"])
        rect(img, 17, 45 + (0 if frame != 2 else -1), 21, 46, c["shoes"])
    else:
        lx0, lx1 = 10 - w // 2, 14
        rx0, rx1 = 17, 21 + w // 2
        rect(img, lx0, 35, lx1, 42 + l_off, c["pants"])
        rect(img, rx0, 35, rx1, 42 + r_off, c["pants"])
        rect(img, lx0, 35, rx1, 37, c["pants"])
        rect(img, rx1 - 1, 35, rx1, 42 + r_off, shade(c["pants"], 0.8))
        if c.get("wraps"):
            rect(img, lx0, 41 + l_off, lx1, 42 + l_off, c["wraps"])
            rect(img, rx0, 41 + r_off, rx1, 42 + r_off, c["wraps"])
        rect(img, lx0 - 1, 43 + l_off, lx1, 46 + l_off, c["shoes"])
        rect(img, rx0, 43 + r_off, rx1 + 1, 46 + r_off, c["shoes"])

    by = bob
    # 몸통
    x0, x1 = 10 - w, 21 + w
    top = c["top"]
    rect(img, x0, 24 + by, x1, 34 + by, top)
    if c.get("belly"):
        ellipse(img, 15, 30 + by, 8 + w // 2, 6, top)
        ellipse(img, 13, 28 + by, 3, 2, shade(top, 1.12))
    rect(img, x1 - 1, 24 + by, x1, 34 + by, shade(top, 0.82))
    if c.get("vest") and not back:
        rect(img, x0, 24 + by, x0 + 4, 34 + by, c["vest"])
        rect(img, x1 - 4, 24 + by, x1, 34 + by, c["vest"])
        if c.get("fur"):
            rect(img, x0 + 4, 24 + by, x0 + 4, 33 + by, c["fur"])
            rect(img, x1 - 4, 24 + by, x1 - 4, 33 + by, c["fur"])
            rect(img, x0, 24 + by, x1, 24 + by, c["fur"])
    elif c.get("vest"):
        rect(img, x0, 24 + by, x1, 34 + by, c["vest"])
    if not back and not c.get("vest") and not c.get("belly"):
        for i in range(5):  # 옷깃
            px(img, 12 + i, 24 + i + by, shade(top, 0.75))
            px(img, 19 - i // 2, 24 + i + by, shade(top, 0.75))
    if c.get("sash"):
        rect(img, x0, 32 + by, x1, 33 + by, c["sash"])
        if not back:
            rect(img, 17, 34 + by, 18, 37 + by, c["sash"])
    if c.get("ribbon") and not back:  # 고름
        rect(img, 15, 27 + by, 16, 28 + by, c["sash"])
        thick_line(img, (16, 29 + by), (17, 33 + by), 1, c["sash"])
    # 팔
    la = {0: 0, 1: -1, 2: 1}[frame]
    for side, ax in ((-1, x0 - 3), (1, x1 + 1)):
        d = la * side
        arm_c = c.get("sleeve") or c["skin"]
        rect(img, ax, 25 + by + d, ax + 2, 31 + by + d, arm_c)
        hand = c.get("glove") or c["skin"]
        rect(img, ax, 32 + by + d, ax + 2, 34 + by + d, hand)
    if c.get("abacus") and not back:
        rect(img, 9, 29 + by, 22, 33 + by, (120, 80, 50, 255))
        rect(img, 10, 30 + by, 21, 32 + by, (70, 46, 30, 255))
        for x in range(11, 21, 2):
            px(img, x, 30 + by, (230, 200, 150, 255))
            px(img, x, 32 + by, (230, 200, 150, 255))
        rect(img, 10, 31 + by, 21, 31 + by, (120, 80, 50, 255))
    # 머리
    hx, hy = 8, 5 + by
    round_head(img, hx, hy, hx + 15, hy + 18, c["skin"])
    rect(img, hx + 2, hy + 18, hx + 13, hy + 18, shade(c["skin"], 0.85))
    if back:
        hair_front(img, c, hx, hy, frame, back=True)
    else:
        face_front(img, c, hx, hy, expr)
        hair_front(img, c, hx, hy, frame)
    if c.get("beard") and not back:
        bc = c["beard"]
        rect(img, hx + 3, hy + 14, hx + 12, hy + 19, bc)
        for i in range(10):
            rect(img, hx + 4 + i // 3, hy + 20 + i, hx + 11 - i // 3, hy + 20 + i, bc)
        rect(img, hx + 2, hy + 13, hx + 13, hy + 13, bc)
        px(img, hx + 7, hy + 15, (150, 80, 70, 255))
        px(img, hx + 8, hy + 15, (150, 80, 70, 255))
    if c.get("staff"):
        rect(img, 26, 14 + by, 27, 46, (120, 82, 50, 255))
        ellipse(img, 27, 12 + by, 3, 3, (200, 120, 50, 255))
        ellipse(img, 27, 8 + by, 2, 2, (200, 120, 50, 255))
        rect(img, 25, 10 + by, 29, 10 + by, (150, 40, 40, 255))
    return outline(img)


# ---------------------------------------------------------------- 옆모습 (관절 포즈)
def head_side(img, c, hx, hy, expr="normal"):
    """왼쪽을 보는 옆얼굴. 머리 상자 hx..hx+15, hy..hy+18."""
    round_head(img, hx, hy, hx + 15, hy + 18, c["skin"])
    px(img, hx - 1, hy + 12, c["skin"])  # 코
    s = c["hair_style"]
    hc = c["hair"]
    if s == "spiky":
        rect(img, hx + 7, hy, hx + 15, hy + 13, hc)   # 뒷머리
        rect(img, hx, hy, hx + 15, hy + 3, hc)        # 윗머리
        rect(img, hx, hy + 4, hx + 1, hy + 5, hc)     # 앞머리
        for i, (sx, sy) in enumerate(((hx + 4, hy - 4), (hx + 9, hy - 5), (hx + 14, hy - 3), (hx + 18, hy + 2))):
            thick_line(img, (sx - 1, sy + 4), (sx, sy), 2, hc)
        rect(img, hx, hy + 6, hx + 15, hy + 7, c["band"])
        thick_line(img, (hx + 15, hy + 7), (hx + 21, hy + 11), 2, c["band"])
        thick_line(img, (hx + 15, hy + 8), (hx + 20, hy + 14), 1, c["band"])
    elif s == "baldknot":
        rect(img, hx + 9, hy - 4, hx + 12, hy - 1, hc)
        rect(img, hx + 9, hy - 1, hx + 12, hy - 1, (150, 40, 40, 255))
    elif s == "gat":
        rect(img, hx + 9, hy + 2, hx + 15, hy + 12, hc)
        rect(img, hx, hy + 3, hx + 15, hy + 4, hc)
        rect(img, hx + 4, hy - 5, hx + 12, hy + 1, c["hat"])
        rect(img, hx - 4, hy + 2, hx + 20, hy + 2, c["hat"])
    elif s == "twinbuns":
        rect(img, hx + 8, hy, hx + 15, hy + 14, hc)
        rect(img, hx, hy, hx + 15, hy + 4, hc)
        circle(img, hx + 13, hy - 1, 3, hc)
        rect(img, hx + 11, hy - 2, hx + 15, hy - 2, c["ribbon"])
    elif s == "bald":
        rect(img, hx + 11, hy + 7, hx + 15, hy + 11, hc)
    # 눈
    ex, ey = hx + 2, hy + 10
    if expr == "hurt":
        thick_line(img, (ex, ey - 1), (ex + 2, ey + 1), 1, EYE)
        thick_line(img, (ex + 2, ey - 1), (ex, ey + 1), 1, EYE)
    elif expr == "happy":
        px(img, ex, ey + 1, EYE)
        px(img, ex + 1, ey, EYE)
        px(img, ex + 2, ey + 1, EYE)
    elif c.get("eyepatch") and False:
        pass
    else:
        rect(img, ex, ey - 1 if expr != "angry" else ey, ex + 1, ey + 1, EYE)
        px(img, ex + 1, ey - 1 if expr != "angry" else ey, WHITE)
    b = c.get("brows")
    bc = c["hair"] if b != "drape" else c.get("beard", WHITE)
    if b == "drape":
        rect(img, ex - 1, ey - 3, ex + 4, ey - 2, bc)
        rect(img, ex - 2, ey - 2, ex - 1, ey + 2, bc)
    else:
        if expr == "angry" or b in ("bold", "unibrow"):
            thick_line(img, (ex - 1, ey - 4), (ex + 3, ey - 2), 1, bc)
        else:
            rect(img, ex, ey - 3, ex + 2, ey - 3, bc)
    if c.get("bandage"):
        rect(img, ex + 3, ey + 3, ex + 5, ey + 4, WHITE)
    if c.get("stubble"):
        for y in range(hy + 15, hy + 18, 2):
            px(img, hx + 3, y, shade(c["skin"], 0.7))
            px(img, hx + 5, y + 1, shade(c["skin"], 0.7))
    # 입
    mx, my = hx + 1, hy + 15
    if expr in ("hurt", "shout"):
        rect(img, mx, my - 1, mx + 2, my + 1, (110, 36, 36, 255))
    elif c.get("mouth") in ("grin", "snaggle") or expr == "happy":
        rect(img, mx, my, mx + 3, my, (110, 36, 36, 255))
        px(img, mx + 1, my, TOOTH)
    elif c.get("mouth") != "beard":
        rect(img, mx + 1, my, mx + 2, my, (150, 70, 60, 255))
    if c.get("mouth") == "mustache":
        rect(img, mx - 1, my - 2, mx + 4, my - 2, c["hair"])
    if c.get("beard"):
        thick_line(img, (hx + 3, hy + 14), (hx + 1, hy + 26), 4, c["beard"])
        rect(img, hx + 1, hy + 13, hx + 6, hy + 16, c["beard"])


def draw_side(c, pose, canvas_w=W, ox=0, expr=None):
    """관절 기반 옆모습 (왼쪽을 봄). pose 는 아래 POSES 의 키."""
    img = new(canvas_w, H)
    P = POSES[pose]
    dx = ox
    j = {k: (v[0] + dx, v[1]) for k, v in P.items() if isinstance(v, tuple)}
    w = c.get("wide", 0)
    pants = c["pants"]
    sleeve = c.get("sleeve") or c["skin"]
    hand = c.get("glove") or c["skin"]
    back_c = shade(sleeve, 0.72)
    # 뒷팔, 뒷다리
    thick_line(img, j["sb"], j["eb"], 3, back_c)
    thick_line(img, j["eb"], j["hb"], 3, back_c)
    rect(img, j["hb"][0] - 1, j["hb"][1] - 1, j["hb"][0] + 1, j["hb"][1] + 1, shade(hand, 0.75))
    if not c.get("skirt") and not c.get("robe"):
        thick_line(img, j["hipb"], j["kb"], 4, shade(pants, 0.72))
        thick_line(img, j["kb"], j["fb"], 4, shade(pants, 0.72))
        rect(img, j["fb"][0] - 3, j["fb"][1] - 1, j["fb"][0] + 1, j["fb"][1] + 1, shade(c["shoes"], 0.8))
    # 몸통
    sx, sy = j["s"]
    hx_, hy_ = j["hip"]
    for t in range(0, 11):
        cx = round(sx + (hx_ - sx) * t / 10)
        cy = round(sy + (hy_ - sy) * t / 10)
        rect(img, cx - 4 - w // 2, cy, cx + 4 + w // 2, cy, c["top"])
    if c.get("belly"):
        ellipse(img, sx - 3, sy + 6, 5 + w // 2, 5, c["top"])
    if c.get("vest"):
        for t in range(0, 11):
            cx = round(sx + (hx_ - sx) * t / 10)
            cy = round(sy + (hy_ - sy) * t / 10)
            rect(img, cx + 1, cy, cx + 4 + w // 2, cy, c["vest"])
    if c.get("sash"):
        rect(img, hx_ - 5 - w // 2, hy_ - 2, hx_ + 4 + w // 2, hy_ - 1, c["sash"])
        if c.get("band"):
            thick_line(img, (hx_ + 4, hy_ - 1), (hx_ + 8, hy_ + 3 + P.get("flutter", 0)), 2, c["sash"])
    if c.get("skirt") or c.get("robe"):
        col = c.get("skirt") or c["top"]
        fx = (j["ff"][0] + j["fb"][0]) // 2
        for y in range(hy_, 45):
            t = (y - hy_) / max(1, 45 - hy_)
            cx = round(hx_ + (fx - hx_) * t)
            sp = 5 + int(t * 3)
            rect(img, cx - sp, y, cx + sp, y, col)
        rect(img, j["ff"][0] - 3, 45, j["ff"][0] + 1, 46, c["shoes"])
    else:
        thick_line(img, j["hipf"], j["kf"], 4, pants)
        thick_line(img, j["kf"], j["ff"], 4, pants)
        if c.get("wraps"):
            rect(img, j["ff"][0] - 1, j["ff"][1] - 3, j["ff"][0] + 1, j["ff"][1] - 2, c["wraps"])
        rect(img, j["ff"][0] - 3, j["ff"][1] - 1, j["ff"][0] + 1, j["ff"][1] + 1, c["shoes"])
    # 머리
    hx, hy = j["head"]
    head_side(img, c, hx, hy, expr or P.get("expr", "normal"))
    # 앞팔
    thick_line(img, j["sf"], j["ef"], 3, sleeve)
    thick_line(img, j["ef"], j["hf"], 3, c["skin"] if c.get("glove") else sleeve)
    big = 2 if P.get("bigfist") else 1
    rect(img, j["hf"][0] - big, j["hf"][1] - big, j["hf"][0] + big, j["hf"][1] + big, hand)
    if P.get("club") and c.get("hair_style") == "baldknot":
        cx0, cy0 = j["hf"]
        ang = P["club"]
        ex = cx0 + round(math.cos(ang) * 16)
        ey = cy0 + round(math.sin(ang) * 16)
        thick_line(img, (cx0, cy0), (ex, ey), 3, (120, 80, 48, 255))
        thick_line(img, (cx0 + round(math.cos(ang) * 10), cy0 + round(math.sin(ang) * 10)), (ex, ey), 5, (140, 96, 58, 255))
    if c.get("staff"):
        hxx, hyy = j["hf"]
        rect(img, hxx, hyy - 18, hxx + 1, 46, (120, 82, 50, 255))
        ellipse(img, hxx + 1, hyy - 20, 3, 3, (200, 120, 50, 255))
    return outline(img)


# 관절 좌표 (왼쪽을 바라봄, 32폭 기준). head=머리 상자 좌상단
_BASE = dict(head=(8, 5), s=(16, 25), hip=(16, 34),
             sf=(14, 26), ef=(13, 30), hf=(13, 33), sb=(18, 26), eb=(19, 30), hb=(19, 33),
             hipf=(14, 35), kf=(13, 39), ff=(13, 44), hipb=(18, 35), kb=(18, 39), fb=(18, 44))


def _pose(**kw):
    d = dict(_BASE)
    d.update(kw)
    return d


POSES = {
    # 필드 걷기 (옆)
    "stand": _pose(),
    "walk1": _pose(ef=(11, 30), hf=(10, 32), eb=(21, 30), hb=(22, 32), kf=(11, 39), ff=(9, 44), kb=(20, 39), fb=(21, 44), flutter=1),
    "walk2": _pose(ef=(20, 30), hf=(21, 32), eb=(12, 30), hb=(11, 32), kf=(19, 39), ff=(20, 44), kb=(12, 39), fb=(10, 44), flutter=-1),
    # 전투
    "ready": _pose(head=(7, 7), s=(15, 27), hip=(16, 35), sf=(13, 28), ef=(9, 29), hf=(6, 25), bigfist=True,
                   sb=(18, 28), eb=(15, 32), hb=(11, 29), hipf=(14, 36), kf=(9, 39), ff=(7, 44),
                   hipb=(18, 36), kb=(21, 40), fb=(23, 44), expr="angry"),
    "punch": _pose(head=(5, 7), s=(13, 27), hip=(16, 35), sf=(11, 28), ef=(4, 28), hf=(-4, 27), bigfist=True,
                   sb=(17, 28), eb=(20, 31), hb=(19, 34), hipf=(13, 36), kf=(7, 39), ff=(4, 44),
                   hipb=(18, 36), kb=(23, 40), fb=(27, 44), expr="shout", flutter=3),
    "kick": _pose(head=(12, 5), s=(19, 25), hip=(19, 34), sf=(17, 26), ef=(23, 24), hf=(27, 22),
                  sb=(21, 26), eb=(25, 29), hb=(28, 30), hipf=(17, 34), kf=(9, 31), ff=(-2, 29),
                  hipb=(21, 35), kb=(21, 40), fb=(22, 44), expr="shout", flutter=3),
    "hurt": _pose(head=(12, 6), s=(19, 26), hip=(17, 35), sf=(17, 27), ef=(21, 23), hf=(23, 19),
                  sb=(21, 27), eb=(25, 25), hb=(28, 22), hipf=(16, 36), kf=(14, 40), ff=(11, 44),
                  hipb=(19, 36), kb=(22, 40), fb=(24, 44), expr="hurt"),
    "guard": _pose(head=(9, 8), s=(16, 28), hip=(17, 36), sf=(14, 29), ef=(9, 26), hf=(9, 20), bigfist=True,
                   sb=(18, 29), eb=(12, 30), hb=(11, 22), hipf=(15, 37), kf=(10, 40), ff=(8, 44),
                   hipb=(19, 37), kb=(22, 41), fb=(23, 44), expr="angry"),
    "win": _pose(sf=(14, 26), ef=(13, 18), hf=(13, 11), bigfist=True, expr="happy",
                 sb=(18, 26), eb=(21, 30), hb=(19, 33)),
    "shout": _pose(sf=(14, 26), ef=(9, 27), hf=(6, 30), sb=(18, 26), eb=(23, 27), hb=(26, 30),
                   kf=(11, 39), ff=(9, 44), kb=(21, 39), fb=(23, 44), expr="shout"),
    # 덕팔 (몽둥이)
    "club_idle": _pose(ef=(12, 30), hf=(11, 29), club=-2.2, expr="normal"),
    "club_windup": _pose(head=(10, 6), s=(18, 26), hip=(17, 35), sf=(16, 27), ef=(19, 21), hf=(21, 16), club=-2.6,
                         kf=(11, 39), ff=(8, 44), kb=(21, 39), fb=(23, 44), expr="angry"),
    "club_swing": _pose(head=(4, 8), s=(12, 28), hip=(15, 35), sf=(10, 29), ef=(5, 31), hf=(1, 33), club=2.6,
                        hipf=(13, 36), kf=(7, 40), ff=(4, 44), kb=(21, 40), fb=(25, 44), expr="angry"),
}


def char_sheet(c):
    sheet = new(W * 3, H * 4)
    rows = [
        [draw_front(c, 0), draw_front(c, 1), draw_front(c, 2)],
        [draw_side(c, "stand"), draw_side(c, "walk1"), draw_side(c, "walk2")],
        None,
        [draw_front(c, 0, back=True), draw_front(c, 1, back=True), draw_front(c, 2, back=True)],
    ]
    rows[2] = [im.transpose(Image.FLIP_LEFT_RIGHT) for im in rows[1]]
    for r, frames in enumerate(rows):
        for f, im in enumerate(frames):
            sheet.paste(im, (f * W, r * H), im)
    return sheet


def portrait(c, expr):
    img = draw_front(c, 0, expr=expr)
    crop = img.crop((0, 0, 32, 32))
    bg = new(32, 32)
    bg.alpha_composite(crop)
    return bg


EXPRS = ["normal", "happy", "angry", "surprised", "sweat"]


def scarecrow_frames():
    from gen_art import WOOD, WOOD_L
    img = new(W, H)
    rect(img, 15, 16, 16, 46, WOOD)
    rect(img, 15, 16, 15, 46, WOOD_L)
    rect(img, 4, 22, 27, 23, WOOD)
    rect(img, 8, 21, 23, 35, (176, 92, 70, 255))
    rect(img, 11, 25, 14, 29, (84, 110, 160, 255))
    rect(img, 18, 30, 21, 33, (200, 180, 90, 255))
    rect(img, 8, 30, 23, 31, (90, 64, 48, 255))
    for x in (9, 12, 16, 19, 22):
        rect(img, x, 36, x, 38, (220, 190, 100, 255))
    for x, y in ((2, 20), (3, 24), (28, 20), (27, 25)):
        rect(img, x, y, x + 1, y, (230, 200, 110, 255))
    ellipse(img, 15, 13, 8, 7, (226, 204, 150, 255))
    rect(img, 10, 11, 12, 13, EYE)                  # 단추 눈
    px(img, 10, 11, WHITE)
    thick_line(img, (17, 10), (20, 13), 1, EYE)     # X 눈
    thick_line(img, (20, 10), (17, 13), 1, EYE)
    for i, x in enumerate(range(9, 22)):             # 꿰맨 큰 웃음
        px(img, x, 17 + (1 if 11 < x < 19 else 0), (150, 60, 50, 255))
        if i % 2 == 0:
            px(img, x, 16 + (1 if 11 < x < 19 else 0), (150, 60, 50, 255))
    for i in range(7):
        rect(img, 15 - i * 2, 2 + i, 16 + i * 2, 2 + i, (220, 180, 90, 255) if i % 2 == 0 else (196, 156, 70, 255))
    rect(img, 2, 8, 29, 8, (160, 120, 60, 255))
    return outline(img)


def build_all():
    for key, c in CHARS.items():
        save(char_sheet(c), f"assets/characters/{key}.png")
        for e in EXPRS:
            save(portrait(c, e), f"assets/portraits/{key}_{e}.png")
    sc = scarecrow_frames()
    save(sc, "assets/characters/scarecrow.png")
    save(sc.crop((0, 0, 32, 32)), "assets/portraits/scarecrow_normal.png")
    # 전투 자세 (48 폭 캔버스, 3배). 도윤은 오른쪽을 보도록 좌우 반전
    d = CHARS["doyun"]
    for pose in ("ready", "punch", "kick", "hurt", "guard", "win", "shout"):
        im = draw_side(d, pose, 48, 10).transpose(Image.FLIP_LEFT_RIGHT)
        save(scale(im, 3), f"assets/battle/doyun_{pose}.png")
    ko = draw_side(d, "hurt", 48, 10).transpose(Image.FLIP_LEFT_RIGHT).rotate(90, expand=False)
    save(scale(ko, 3), "assets/battle/doyun_ko.png")
    b = CHARS["bandit"]
    for pose, name in (("club_idle", "idle"), ("club_windup", "windup"), ("club_swing", "attack"), ("hurt", "hurt")):
        save(scale(draw_side(b, pose, 48, 8), 3), f"assets/battle/bandit_{name}.png")
    save(scale(draw_side(b, "hurt", 48, 8).rotate(-90), 3), "assets/battle/bandit_ko.png")
    sc48 = new(48, 48)
    sc48.alpha_composite(sc, (8, 0))
    save(scale(sc48, 3), "assets/battle/scarecrow_idle.png")
    save(scale(sc48.rotate(12, center=(24, 46)), 3), "assets/battle/scarecrow_windup.png")
    save(scale(sc48.rotate(-25, center=(24, 46)), 3), "assets/battle/scarecrow_attack.png")
    save(scale(sc48.rotate(-10, center=(24, 46)), 3), "assets/battle/scarecrow_hurt.png")
    save(scale(sc48.rotate(-80, center=(24, 40)), 3), "assets/battle/scarecrow_ko.png")
    # 아이콘
    face = draw_front(d, 0, expr="happy").crop((4, 0, 28, 24))
    from gen_art import PAPER, VERMILION
    bg = new(128, 128, PAPER)
    circle(bg, 64, 64, 60, VERMILION)
    bg.alpha_composite(face.resize((120, 120), Image.NEAREST), (4, 6))
    save(bg, "icon.png")


def build_fx():
    """전투 이펙트 텍스처."""
    imp = new(48, 48)
    for k in range(12):
        a = k * math.pi / 6
        r = 22 if k % 2 == 0 else 12
        thick_line(imp, (24, 24), (24 + round(math.cos(a) * r), 24 + round(math.sin(a) * r)), 3 if k % 2 == 0 else 2, (255, 240, 200, 255))
    circle(imp, 24, 24, 6, (255, 255, 240, 255))
    save(imp, "assets/fx/impact.png")
    ring = new(64, 64)
    for y in range(64):
        for x in range(64):
            d = math.hypot(x - 31.5, y - 31.5)
            if 26 <= d <= 30:
                ring.putpixel((x, y), (255, 214, 120, 255))
            elif 23 <= d < 26:
                ring.putpixel((x, y), (255, 170, 80, 150))
    save(ring, "assets/fx/ring.png")
    wind = new(64, 64)
    for k in range(3):
        for t in range(60):
            a = math.pi * (0.15 + 0.7 * t / 60)
            r = 26 - k * 5
            x = 32 + round(math.cos(a) * r)
            y = 32 - round(math.sin(a) * r * 0.6)
            alpha = int(255 * (1 - abs(t - 30) / 32))
            rect(wind, x, y, x + 1, y + 1, (210, 240, 230, alpha))
    save(wind, "assets/fx/wind.png")
    shield = new(64, 64)
    for y in range(64):
        for x in range(64):
            d = math.hypot((x - 31.5) / 1.0, (y - 31.5) / 1.2)
            if 24 <= d <= 27:
                shield.putpixel((x, y), (180, 210, 255, 220))
            elif d < 24:
                shield.putpixel((x, y), (140, 180, 240, 50))
    save(shield, "assets/fx/shield.png")
    wisp = new(16, 16)
    circle(wisp, 8, 8, 5, (130, 190, 255, 160))
    circle(wisp, 8, 8, 2, (230, 245, 255, 255))
    save(wisp, "assets/fx/wisp.png")
    target = new(64, 64)
    for y in range(64):
        for x in range(64):
            d = math.hypot(x - 31.5, y - 31.5)
            if 28 <= d <= 31:
                target.putpixel((x, y), (255, 255, 255, 255))
    save(target, "assets/fx/target_ring.png")

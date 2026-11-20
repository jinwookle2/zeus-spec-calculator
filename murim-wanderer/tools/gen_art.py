#!/usr/bin/env python3
"""무림유랑기 픽셀아트 생성기 (v2: 진지한 무협풍).

외부 에셋 없이 모든 프로토타입 그래픽을 코드로 생성한다.
결과물은 전부 이 프로젝트의 독창적 창작물이며 상업적 이용에 제한이 없다.

- 캐릭터: 32x48 셀, 4방향(하/좌/우/상) x 3프레임(정지/걸음1/걸음2)
- 타일: 32x32, 차분한 먹색·황토 계열 팔레트
- 배경: 수묵화 느낌의 640x360

사용법 (프로젝트 루트에서):  python3 tools/gen_art.py      (필요: Pillow)
"""
from __future__ import annotations

import os
import random
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = 32          # 타일 크기
CW, CH = 32, 48  # 캐릭터 셀 크기

# ---------------------------------------------------------------- 팔레트 (차분한 무협풍)
OUT = (28, 22, 26, 255)
CLEAR = (0, 0, 0, 0)
SKIN = (226, 186, 150, 255)
SKIN_D = (190, 146, 116, 255)
EYE = (24, 18, 22, 255)

GRASS = (92, 124, 74, 255)
GRASS_D = (70, 100, 60, 255)
GRASS_L = (116, 146, 88, 255)
DIRT = (158, 136, 104, 255)
DIRT_D = (130, 110, 84, 255)
DIRT_L = (178, 158, 124, 255)
STONE = (140, 138, 132, 255)
STONE_D = (104, 102, 100, 255)
STONE_L = (172, 168, 160, 255)
WOOD = (110, 74, 50, 255)
WOOD_D = (74, 50, 36, 255)
WOOD_L = (142, 100, 68, 255)
PINE = (52, 92, 66, 255)
PINE_D = (32, 62, 48, 255)
PINE_L = (82, 120, 82, 255)
BARK = (124, 78, 56, 255)
WATER = (64, 104, 112, 255)
WATER_D = (46, 80, 90, 255)
WATER_L = (120, 156, 154, 255)
PLASTER = (208, 198, 176, 255)
PLASTER_D = (176, 164, 144, 255)
SAND = (188, 170, 134, 255)
SAND_D = (162, 144, 110, 255)
PAPER = (226, 216, 192, 255)
VERMILION = (168, 46, 36, 255)

ROOFS = {  # (기본, 어두움, 밝음) — 먹빛 기와
    "red": ((82, 82, 90, 255), (54, 54, 62, 255), (116, 116, 124, 255)),
    "blue": ((60, 66, 84, 255), (38, 42, 56, 255), (92, 100, 120, 255)),
    "green": ((70, 92, 84, 255), (46, 64, 58, 255), (100, 124, 112, 255)),
}


def new(w, h, color=CLEAR):
    return Image.new("RGBA", (w, h), color)


def rect(img, x0, y0, x1, y1, c):
    """x0..x1, y0..y1 포함 사각형 (범위 밖은 자름)."""
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    for y in range(max(0, y0), min(img.height, y1 + 1)):
        for x in range(max(0, x0), min(img.width, x1 + 1)):
            img.putpixel((x, y), c)


def px(img, x, y, c):
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), c)


def circle(img, cx, cy, r, c):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r * 0.6:
                px(img, x, y, c)


def ellipse(img, cx, cy, rx, ry, c):
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            if ((x - cx) / max(rx, 0.5)) ** 2 + ((y - cy) / max(ry, 0.5)) ** 2 <= 1.0:
                px(img, x, y, c)


def outline(img, color=OUT):
    """불투명 픽셀 주변 투명 픽셀에 외곽선."""
    src = img.copy()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            if src.getpixel((x, y))[3] != 0:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and src.getpixel((nx, ny))[3] != 0 and src.getpixel((nx, ny)) != color:
                    img.putpixel((x, y), color)
                    break
    return img


def scale(img, f):
    return img.resize((img.width * f, img.height * f), Image.NEAREST)


def save(img, rel):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print("wrote", rel, img.size)


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3]) + (255,)


# ---------------------------------------------------------------- 캐릭터 (32x48)
class Look:
    def __init__(self, **kw):
        self.hair = (30, 26, 32, 255)
        self.style = "topknot"     # topknot | bun | hat | bandana
        self.band = None           # 머리띠 색
        self.robe = (46, 58, 92, 255)
        self.robe_d = (32, 40, 66, 255)
        self.trim = (214, 206, 186, 255)   # 안깃/소매 끝
        self.sash = (150, 40, 40, 255)
        self.pants = (40, 40, 48, 255)
        self.boots = (46, 34, 30, 255)
        self.beard = None
        self.mustache = None
        self.brows = None
        self.wide = 0
        self.skirt = None          # 치마 색 (여성 한복)
        self.hat = (26, 24, 28, 255)
        self.eyepatch = False
        self.scar = False
        self.long_robe = True      # 무릎 아래까지 오는 두루마기
        self.__dict__.update(kw)


def draw_char(look: Look, facing: str, frame: int) -> Image.Image:
    """facing: down/up/left. frame: 0=정지, 1/2=걷기. 발 바닥은 y=46."""
    img = new(CW, CH)
    side = facing == "left"
    w = look.wide
    bob = -1 if frame in (1, 2) else 0
    robe, robe_d = look.robe, look.robe_d

    # --- 다리 / 신발 (짧은 상의면 허리 아래부터 바지)
    lt = 38 if look.long_robe else 28
    if look.skirt:
        sk = look.skirt
        sway = {0: 0, 1: -1, 2: 1}[frame]
        rect(img, 10 - w, 27, 21 + w, 44, sk)
        for i in range(4):  # 아래로 퍼지는 치마
            rect(img, 9 - w - (1 if i > 1 else 0) + sway, 38 + i * 2, 22 + w + (1 if i > 1 else 0) + sway, 39 + i * 2, sk)
        rect(img, 18 + w, 28, 21 + w, 45, shade(sk, 0.8))
        rect(img, 9 - w, 45, 22 + w, 45, shade(sk, 0.7))
        rect(img, 12, 46, 14, 46, look.boots)
        rect(img, 17, 46, 19, 46, look.boots)
    elif side:
        if frame == 0:
            rect(img, 13, lt, 18, 43, look.pants)
            rect(img, 12, 44, 18, 46, look.boots)
        else:
            front, back = (9, 13), (17, 21)
            if frame == 2:
                front, back = back, front
            rect(img, 13, lt, 18, 37, look.pants)
            rect(img, back[0] + 1, 38, back[1], 43, shade(look.pants, 0.75))
            rect(img, back[0], 44, back[1], 46, shade(look.boots, 0.8))
            rect(img, front[0] + 1, 38, front[1], 43, look.pants)
            rect(img, front[0], 44, front[1], 46, look.boots)
    else:
        l_off = -1 if frame == 1 else 0
        r_off = -1 if frame == 2 else 0
        rect(img, 11, lt, 14, 43 + l_off, look.pants)
        rect(img, 17, lt, 20, 43 + r_off, look.pants)
        if lt < 38:
            rect(img, 11, lt, 20, lt + 3, look.pants)
        rect(img, 10, 44 + l_off, 14, 46 + l_off, look.boots)
        rect(img, 17, 44 + r_off, 21, 46 + r_off, look.boots)

    by = bob
    # --- 아래 도포 자락
    if look.long_robe and not look.skirt:
        hem = 37
        if side:
            sway = {0: 0, 1: -1, 2: 1}[frame]
            rect(img, 11 + sway, 28 + by, 20 + sway, hem, robe)
            rect(img, 18 + sway, 28 + by, 20 + sway, hem, robe_d)
            rect(img, 11 + sway, hem, 20 + sway, hem, robe_d)
        else:
            rect(img, 10 - w, 28 + by, 21 + w, hem, robe)
            rect(img, 20 + w, 28 + by, 21 + w, hem, robe_d)
            rect(img, 10 - w, hem, 21 + w, hem, robe_d)
            if facing == "down":
                rect(img, 15, 32, 16, hem, look.pants)  # 앞트임
                rect(img, 14, 32, 14, hem, robe_d)

    # --- 몸통
    if side:
        rect(img, 12, 17 + by, 19, 27 + by, robe)
        rect(img, 18, 17 + by, 19, 27 + by, robe_d)
        px(img, 12, 17 + by, CLEAR)
        for i in range(5):  # 옷깃
            px(img, 12 + i // 2, 17 + i + by, look.trim)
        rect(img, 12, 26 + by, 19, 27 + by, look.sash)
        if not look.skirt:
            rect(img, 19, 27 + by, 20, 31 + by, look.sash)  # 띠 매듭 뒤로
        sw = {0: 0, 1: 2, 2: -2}[frame]
        rect(img, 14 + sw, 18 + by, 17 + sw, 27 + by, robe_d)  # 팔(소매)
        rect(img, 14 + sw, 28 + by, 17 + sw, 28 + by, look.trim)
        rect(img, 15 + sw, 29 + by, 16 + sw, 30 + by, SKIN)
    else:
        rect(img, 10 - w, 17 + by, 21 + w, 27 + by, robe)
        rect(img, 20 + w, 17 + by, 21 + w, 27 + by, robe_d)
        px(img, 10 - w, 17 + by, CLEAR)
        px(img, 21 + w, 17 + by, CLEAR)
        if facing == "down":
            for i in range(6):  # 교차 옷깃 (좌임 아닌 우임)
                px(img, 12 + i, 17 + i + by, look.trim)
                px(img, 13 + i, 17 + i + by, look.trim)
            for i in range(3):
                px(img, 19 - i, 17 + i + by, look.trim)
        else:
            rect(img, 15, 18 + by, 16, 25 + by, robe_d)  # 등솔기
        rect(img, 10 - w, 26 + by, 21 + w, 27 + by, look.sash)
        if facing == "down" and not look.skirt:
            rect(img, 17, 28 + by, 18, 32 + by, look.sash)  # 띠 자락
        la = {0: 0, 1: -1, 2: 1}[frame]
        for x0 in (7 - w, 22 + w):  # 넓은 소매
            d = la if x0 < 16 else -la
            rect(img, x0, 18 + by + d, x0 + 2, 28 + by + d, robe_d)
            rect(img, x0, 28 + by + d, x0 + 2, 28 + by + d, look.trim)
            rect(img, x0 + (1 if x0 < 16 else 0), 29 + by + d, x0 + (2 if x0 < 16 else 1), 30 + by + d, SKIN)

    # --- 목 / 머리
    rect(img, 15, 16 + by, 16, 16 + by, SKIN_D)
    hx0, hx1 = (11, 18) if side else (12, 19)
    hy0, hy1 = 6 + by, 15 + by
    rect(img, hx0, hy0, hx1, hy1, SKIN)
    for cx, cy in ((hx0, hy0), (hx1, hy0), (hx0, hy1), (hx1, hy1)):
        px(img, cx, cy, CLEAR)
    rect(img, hx0 + 1, hy1, hx1 - 1, hy1, SKIN_D)

    hair = look.hair
    hair_l = shade(hair, 1.6) if hair[0] < 120 else shade(hair, 1.08)
    if look.style in ("topknot", "bun"):
        if facing == "up":
            rect(img, hx0, hy0, hx1, hy1 - 1, hair)
        elif side:
            rect(img, hx0, hy0, hx1, hy0 + 2, hair)
            rect(img, hx0 + 4, hy0, hx1, hy0 + 7, hair)
        else:
            rect(img, hx0, hy0, hx1, hy0 + 2, hair)
            rect(img, hx0, hy0 + 3, hx0, hy0 + 6, hair)
            rect(img, hx1, hy0 + 3, hx1, hy0 + 6, hair)
        rect(img, hx0 + 1, hy0, hx0 + 3, hy0, hair_l)
    if look.style == "topknot":
        tx = 14 if not side else 15
        rect(img, tx, hy0 - 4, tx + 3, hy0 - 1, hair)
        rect(img, tx, hy0 - 1, tx + 3, hy0 - 1, look.band or (90, 70, 50, 255))
        px(img, tx + 1, hy0 - 4, hair_l)
    elif look.style == "bun":
        bx = 13 if not side else 16
        rect(img, bx, hy0 - 3, bx + 5, hy0, hair)
        rect(img, bx - 1, hy0 - 2, bx + 6, hy0 - 2, (200, 170, 90, 255))  # 비녀
    elif look.style == "hat":  # 갓
        rect(img, hx0 + 1, hy0 - 5, hx1 - 1, hy0 + 1, look.hat)
        rect(img, hx0 + 2, hy0 - 3, hx1 - 2, hy0 - 2, shade(look.hat, 1.8))
        rect(img, hx0 - 5, hy0 + 2, hx1 + 5, hy0 + 2, look.hat)
        rect(img, hx0 - 4, hy0 + 1, hx1 + 4, hy0 + 1, shade(look.hat, 1.5))
        if facing != "up":
            px(img, hx0 + 1, hy0 + 7, look.hat)  # 갓끈
            px(img, hx1 - 1, hy0 + 7, look.hat)
        else:
            rect(img, hx0, hy0 + 3, hx1, hy1 - 1, look.hair)
    elif look.style == "bandana":
        rect(img, hx0, hy0, hx1, hy0 + 3, look.hat)
        rect(img, hx0 + 1, hy0 + 1, hx0 + 2, hy0 + 1, shade(look.hat, 1.4))
        if facing == "up":
            rect(img, hx0, hy0 + 4, hx1, hy1 - 1, look.hair)
            rect(img, 15, hy0 + 4, 16, hy0 + 8, look.hat)
        elif side:
            rect(img, hx1 + 1, hy0 + 2, hx1 + 2, hy0 + 6, look.hat)

    if look.band:
        rect(img, hx0, hy0 + 3, hx1, hy0 + 3, look.band)
        if facing == "up":
            px(img, 15, hy0 + 4, look.band)
            rect(img, 15, hy0 + 5, 15, hy0 + 9, look.band)
            rect(img, 16, hy0 + 4, 16, hy0 + 8, look.band)
        elif side:
            px(img, hx1 + 1, hy0 + 3, look.band)
            px(img, hx1 + 2, hy0 + 4, look.band)
            px(img, hx1 + 2, hy0 + 5, look.band)

    brow = look.brows or look.hair
    if facing == "down":
        ey = hy0 + 5
        rect(img, 13, ey, 14, ey, EYE)  # 가늘고 날카로운 눈
        rect(img, 17, ey, 18, ey, EYE)
        px(img, 14, ey - 1, brow)
        px(img, 13, ey - 2, brow)
        px(img, 17, ey - 1, brow)
        px(img, 18, ey - 2, brow)
        rect(img, 15, ey + 3, 16, ey + 3, SKIN_D)
        if look.eyepatch:
            rect(img, 16, ey - 1, 19, ey + 1, EYE)
            rect(img, hx0, ey - 2, hx0 + 3, ey - 2, EYE)
        if look.scar:
            px(img, 13, ey + 1, (150, 80, 70, 255))
            px(img, 14, ey + 2, (150, 80, 70, 255))
    elif side:
        ey = hy0 + 5
        rect(img, 12, ey, 13, ey, EYE)
        px(img, 13, ey - 1, brow)
        px(img, hx0 - 1, ey + 1, SKIN)  # 코
        px(img, 12, ey + 3, SKIN_D)
    if look.mustache and facing != "up":
        if side:
            rect(img, 10, hy0 + 7, 13, hy0 + 7, look.mustache)
        else:
            rect(img, 13, hy0 + 7, 18, hy0 + 7, look.mustache)
            px(img, 12, hy0 + 8, look.mustache)
            px(img, 19, hy0 + 8, look.mustache)
    if look.beard and facing != "up":
        b = look.beard
        if side:
            rect(img, 10, hy0 + 7, 13, hy1 + 3, b)
            rect(img, 11, hy1 + 4, 13, hy1 + 7, b)
        else:
            rect(img, 12, hy0 + 7, 19, hy1 + 2, b)
            rect(img, 13, hy1 + 3, 18, hy1 + 5, b)
            rect(img, 14, hy1 + 6, 17, hy1 + 8, b)
            rect(img, 15, hy1 + 9, 16, hy1 + 10, b)
            rect(img, 15, hy0 + 8, 16, hy0 + 8, SKIN_D)

    return outline(img)


def char_sheet(look: Look) -> Image.Image:
    sheet = new(CW * 3, CH * 4)
    for row, facing in enumerate(["down", "left", "right", "up"]):
        for f in range(3):
            if facing == "right":
                fr = draw_char(look, "left", f).transpose(Image.FLIP_LEFT_RIGHT)
            else:
                fr = draw_char(look, facing, f)
            sheet.paste(fr, (f * CW, row * CH), fr)
    return sheet


LOOKS = {
    "doyun": Look(band=(160, 36, 36, 255)),
    "master": Look(
        hair=(222, 222, 216, 255), brows=(240, 240, 236, 255), beard=(232, 232, 226, 255),
        robe=(186, 186, 180, 255), robe_d=(146, 148, 146, 255), trim=(92, 84, 78, 255),
        sash=(70, 60, 56, 255), pants=(96, 98, 104, 255),
    ),
    "villager": Look(
        style="bun", hair=(34, 28, 30, 255), robe=(146, 166, 142, 255), robe_d=(116, 136, 116, 255),
        trim=(236, 228, 210, 255), sash=(150, 52, 60, 255), skirt=(54, 62, 96, 255),
        long_robe=False, boots=(220, 214, 200, 255),
    ),
    "merchant": Look(
        style="hat", wide=2, mustache=(30, 26, 32, 255), robe=(140, 108, 70, 255),
        robe_d=(108, 80, 52, 255), trim=(220, 210, 186, 255), sash=(60, 84, 70, 255),
        pants=(80, 66, 54, 255),
    ),
    "bandit": Look(
        style="bandana", hat=(110, 36, 36, 255), wide=1, eyepatch=True, scar=True,
        mustache=(40, 30, 30, 255), robe=(110, 82, 56, 255), robe_d=(82, 60, 42, 255),
        trim=(150, 130, 100, 255), sash=(52, 44, 38, 255), pants=(64, 62, 66, 255),
        long_robe=False,
    ),
}


def draw_scarecrow() -> Image.Image:
    img = new(CW, CH)
    rect(img, 15, 14, 16, 46, WOOD)
    rect(img, 15, 14, 15, 46, WOOD_L)
    rect(img, 5, 20, 26, 21, WOOD)
    rect(img, 9, 19, 22, 34, (120, 96, 70, 255))  # 해진 도포
    rect(img, 9, 34, 22, 34, (96, 74, 54, 255))
    for x in (10, 13, 17, 20):
        px(img, x, 35, (120, 96, 70, 255))
    rect(img, 12, 24, 14, 27, (84, 92, 110, 255))  # 덧댄 천
    rect(img, 9, 28, 22, 29, (70, 56, 44, 255))
    for x in (4, 27):
        rect(img, x, 19, x, 23, (200, 176, 110, 255))
    rect(img, 11, 9, 20, 18, (204, 186, 140, 255))  # 자루 머리
    rect(img, 13, 12, 14, 12, EYE)
    rect(img, 17, 12, 18, 12, EYE)
    rect(img, 13, 16, 18, 16, (120, 80, 64, 255))
    for x in (14, 16):
        px(img, x, 15, (120, 80, 64, 255))
    # 삿갓
    for i in range(6):
        rect(img, 15 - i * 2, 3 + i, 16 + i * 2, 3 + i, (178, 150, 96, 255) if i % 2 == 0 else (156, 128, 80, 255))
    rect(img, 4, 9, 27, 9, (130, 104, 66, 255))
    return outline(img)


# ---------------------------------------------------------------- 타일
def grass_base(seed=0):
    r = random.Random(seed)
    img = new(T, T, GRASS)
    for _ in range(16):
        x, y = r.randrange(1, 31), r.randrange(2, 31)
        c = GRASS_D if r.random() < 0.65 else GRASS_L
        px(img, x, y, c)
        px(img, x - 1, y - 1, c)
        px(img, x + 1, y - 1, c)
    return img


def tile_flowers():
    img = grass_base(1)
    r = random.Random(7)
    for c in ((186, 90, 80, 255), (210, 190, 120, 255), (230, 224, 210, 255), (186, 90, 80, 255)):
        x, y = r.randrange(3, 29), r.randrange(3, 29)
        px(img, x, y, (226, 206, 130, 255))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            px(img, x + dx, y + dy, c)
    return img


def tile_dirt(seed=3):
    r = random.Random(seed)
    img = new(T, T, DIRT)
    for _ in range(14):
        x, y = r.randrange(0, 31), r.randrange(0, 31)
        rect(img, x, y, x + 1, y, DIRT_D if r.random() < 0.6 else DIRT_L)
    return img


def tile_sand():
    r = random.Random(9)
    img = new(T, T, SAND)
    for _ in range(16):
        x, y = r.randrange(0, 31), r.randrange(0, 31)
        px(img, x, y, SAND_D if r.random() < 0.7 else (204, 188, 154, 255))
    return img


def tile_stone_floor():
    img = new(T, T, STONE_L)
    rect(img, 0, 15, 31, 15, STONE_D)
    rect(img, 0, 31, 31, 31, STONE_D)
    rect(img, 15, 0, 15, 15, STONE_D)
    rect(img, 7, 16, 7, 31, STONE_D)
    rect(img, 23, 16, 23, 31, STONE_D)
    for x, y in ((3, 4), (20, 9), (11, 22), (27, 26)):
        px(img, x, y, STONE)
    return img


def tile_tree():
    """소나무."""
    img = grass_base(4)
    top = new(T, T)
    rect(top, 14, 18, 17, 30, BARK)
    rect(top, 14, 18, 14, 30, shade(BARK, 0.75))
    px(top, 16, 24, shade(BARK, 0.7))
    rect(top, 17, 15, 20, 16, BARK)  # 가지
    for cx, cy, rx, ry in ((16, 6, 7, 3), (11, 11, 7, 3), (21, 12, 7, 3), (15, 17, 9, 3)):
        ellipse(top, cx, cy, rx, ry, PINE_D)
        ellipse(top, cx - 1, cy - 1, rx - 1, ry - 1, PINE)
        rect(top, cx - rx + 2, cy - ry + 1, cx - 1, cy - ry + 1, PINE_L)
    outline(top)
    rect(img, 8, 29, 24, 30, GRASS_D)
    img.alpha_composite(top)
    return img


def tile_bush():
    img = grass_base(6)
    top = new(T, T)
    ellipse(top, 16, 20, 11, 8, PINE_D)
    ellipse(top, 15, 19, 9, 6, PINE)
    rect(top, 9, 15, 14, 15, PINE_L)
    outline(top)
    img.alpha_composite(top)
    return img


def tile_rock():
    img = grass_base(8)
    top = new(T, T)
    ellipse(top, 16, 19, 11, 9, STONE_D)
    ellipse(top, 15, 18, 9, 7, STONE)
    rect(top, 10, 14, 15, 14, STONE_L)
    rect(top, 18, 20, 22, 20, STONE_D)
    outline(top)
    img.alpha_composite(top)
    return img


def tile_fence():
    img = grass_base(10)
    top = new(T, T)
    for x in (3, 26):
        rect(top, x, 6, x + 3, 29, WOOD)
        rect(top, x, 6, x, 29, WOOD_L)
    rect(top, 0, 11, 31, 13, WOOD_L)
    rect(top, 0, 20, 31, 22, WOOD)
    rect(top, 0, 13, 31, 13, WOOD_D)
    rect(top, 0, 22, 31, 22, WOOD_D)
    img.alpha_composite(top)
    return img


def tile_water(seed=0):
    img = new(T, T, WATER)
    r = random.Random(11 + seed)
    for _ in range(4):
        x, y = r.randrange(2, 24), r.randrange(2, 30)
        rect(img, x, y, x + 5, y, WATER_L)
        rect(img, x + 1, y + 1, x + 4, y + 1, WATER_D)
    return img


def tile_wall(window=False):
    img = new(T, T, PLASTER)
    rect(img, 0, 0, 31, 3, WOOD_D)
    rect(img, 0, 0, 2, 31, WOOD)
    rect(img, 29, 0, 31, 31, WOOD)
    rect(img, 0, 26, 31, 31, STONE)
    for x in range(0, 32, 8):
        rect(img, x, 26, x, 31, STONE_D)
    rect(img, 0, 26, 31, 26, STONE_D)
    rect(img, 3, 4, 28, 5, PLASTER_D)
    if window:
        rect(img, 8, 8, 23, 21, WOOD_D)
        rect(img, 10, 10, 21, 19, (226, 214, 184, 255))
        for x in (13, 15, 18):
            rect(img, x, 10, x, 19, WOOD)
        rect(img, 10, 14, 21, 15, WOOD)
    return img


def tile_door():
    img = tile_wall()
    rect(img, 7, 6, 24, 31, WOOD_D)
    rect(img, 9, 8, 15, 31, WOOD)
    rect(img, 16, 8, 22, 31, WOOD)
    rect(img, 9, 8, 9, 31, WOOD_L)
    rect(img, 16, 8, 16, 31, WOOD_L)
    px(img, 14, 20, (190, 160, 80, 255))
    px(img, 17, 20, (190, 160, 80, 255))
    return img


def tile_roof(color, eave=False):
    base, dark, light = ROOFS[color]
    img = new(T, T, base)
    for x0 in range(0, 32, 6):  # 세로 기와골
        rect(img, x0, 0, x0, 31, dark)
        rect(img, x0 + 2, 0, x0 + 2, 31, light)
    for y0 in range(0, 32, 8):
        rect(img, 0, y0 + 7, 31, y0 + 7, dark)
    if eave:
        rect(img, 0, 21, 31, 24, dark)
        for x0 in range(0, 32, 6):  # 막새
            rect(img, x0 + 1, 22, x0 + 3, 23, light)
        rect(img, 0, 25, 31, 31, (44, 34, 32, 255))  # 처마 그늘
        for x in range(1, 32, 5):
            rect(img, x, 25, x + 1, 28, WOOD_D)  # 서까래
    else:
        rect(img, 0, 0, 31, 1, dark)
    return img


def tile_sign():
    img = tile_dirt(12)
    top = new(T, T)
    rect(top, 15, 16, 16, 30, WOOD_D)
    rect(top, 5, 6, 26, 17, WOOD_L)
    rect(top, 5, 17, 26, 17, WOOD_D)
    for y in (9, 12, 15):
        rect(top, 8, y, 23, y, WOOD_D)
    outline(top)
    img.alpha_composite(top)
    return img


def tile_stone_wall():
    img = new(T, T, STONE)
    for row, y0 in enumerate(range(0, 32, 8)):
        rect(img, 0, y0 + 7, 31, y0 + 7, STONE_D)
        off = 0 if row % 2 == 0 else 8
        for x in range(off, 32, 16):
            rect(img, x, y0, x, y0 + 7, STONE_D)
        rect(img, off + 2, y0 + 1, off + 5, y0 + 1, STONE_L)
    return img


def tile_jar():
    img = tile_dirt(13)
    top = new(T, T)
    ellipse(top, 16, 20, 9, 9, (96, 66, 50, 255))
    ellipse(top, 13, 17, 3, 3, (128, 92, 68, 255))
    rect(top, 11, 8, 20, 11, (84, 56, 44, 255))
    rect(top, 12, 8, 19, 8, (50, 34, 28, 255))
    rect(top, 8, 18, 24, 18, (76, 50, 40, 255))
    outline(top)
    img.alpha_composite(top)
    return img


def tile_post():
    img = tile_sand()
    top = new(T, T)
    rect(top, 12, 4, 19, 29, WOOD)
    rect(top, 12, 4, 13, 29, WOOD_L)
    rect(top, 18, 4, 19, 29, WOOD_D)
    rect(top, 6, 11, 25, 13, WOOD_D)
    rect(top, 6, 19, 25, 21, WOOD_D)
    rect(top, 14, 7, 17, 9, VERMILION)
    outline(top)
    img.alpha_composite(top)
    return img


def tile_well():
    img = tile_stone_floor()
    top = new(T, T)
    circle(top, 16, 18, 11, STONE_D)
    circle(top, 16, 18, 9, STONE)
    circle(top, 16, 18, 6, WATER_D)
    circle(top, 15, 17, 2, WATER_L)
    rect(top, 4, 3, 5, 18, WOOD)
    rect(top, 26, 3, 27, 18, WOOD)
    rect(top, 3, 2, 28, 4, WOOD_D)
    outline(top)
    img.alpha_composite(top)
    return img


def tile_lantern():
    img = tile_stone_floor()
    top = new(T, T)
    rect(top, 14, 18, 17, 29, STONE_D)
    rect(top, 10, 27, 21, 29, STONE)
    rect(top, 11, 8, 20, 17, STONE)
    rect(top, 13, 10, 18, 15, (232, 190, 110, 255))
    rect(top, 9, 5, 22, 7, STONE_D)
    rect(top, 13, 3, 18, 4, STONE_D)
    outline(top)
    img.alpha_composite(top)
    return img


# 타일 인덱스 순서는 data/maps/tiles.json 과 일치해야 한다.
TILES = [
    ("grass", lambda: grass_base(0)),
    ("flowers", tile_flowers),
    ("dirt", tile_dirt),
    ("stone_floor", tile_stone_floor),
    ("tree", tile_tree),
    ("bush", tile_bush),
    ("rock", tile_rock),
    ("fence", tile_fence),
    ("water", tile_water),
    ("wall", tile_wall),
    ("wall_window", lambda: tile_wall(True)),
    ("door", tile_door),
    ("roof_red", lambda: tile_roof("red")),
    ("eave_red", lambda: tile_roof("red", True)),
    ("roof_blue", lambda: tile_roof("blue")),
    ("eave_blue", lambda: tile_roof("blue", True)),
    ("roof_green", lambda: tile_roof("green")),
    ("eave_green", lambda: tile_roof("green", True)),
    ("sign", tile_sign),
    ("sand", tile_sand),
    ("stone_wall", tile_stone_wall),
    ("jar", tile_jar),
    ("post", tile_post),
    ("well", tile_well),
    ("lantern", tile_lantern),
]


def build_tileset():
    cols = 8
    rows = (len(TILES) + cols - 1) // cols
    sheet = new(cols * T, rows * T)
    for i, (_, fn) in enumerate(TILES):
        sheet.paste(fn(), ((i % cols) * T, (i // cols) * T))
    save(sheet, "assets/tilesets/cheongpung_tiles.png")


# ---------------------------------------------------------------- 수묵화 배경
def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def gradient(img, top, bottom, y0, y1, bands=12):
    for y in range(y0, y1):
        t = int((y - y0) / max(1, y1 - y0) * bands) / bands
        rect(img, 0, y, img.width - 1, y, lerp(top, bottom, t))


def ridge(img, base_y, amp, color, seed, step=6, mist=None, mist_h=6):
    """산 능선. mist 가 주어지면 산 아래쪽을 안개색으로 흐린다."""
    r = random.Random(seed)
    w = img.width
    h = base_y
    target = base_y
    tops = []
    for x in range(w):
        if x % step == 0:
            target = base_y - r.randint(0, amp)
        h += (target > h) - (target < h)
        tops.append(h)
        rect(img, x, h, x, img.height - 1, color)
    if mist:
        for x, t in enumerate(tops):
            for i in range(mist_h):
                y = base_y + 4 + i
                if y >= t and r.random() < 0.35 + i * 0.1:
                    px(img, x, y, mist)
            rect(img, x, base_y + 4 + mist_h, x, base_y + 4 + mist_h + 3, mist)


def pine_silhouette(img, x, y, size, color):
    rect(img, x, y, x + 1, y + size * 3, color)
    for i, (dx, wdt) in enumerate(((2, size * 2), (-size, size * 2), (1, size * 2 + 2))):
        cy = y + i * size
        rect(img, x + dx - wdt // 2, cy, x + dx + wdt // 2, cy + 1, color)
        rect(img, x + dx - wdt // 2 + 1, cy - 1, x + dx + wdt // 2 - 1, cy - 1, color)


def build_title_bg():
    img = new(320, 180, PAPER)
    gradient(img, (232, 222, 198), (214, 200, 172), 0, 180, bands=10)
    circle(img, 236, 58, 18, (178, 58, 42, 255))  # 붉은 해
    ridge(img, 92, 34, (192, 184, 168, 255), 1, 7, mist=(222, 212, 188, 255))
    ridge(img, 118, 30, (150, 144, 134, 255), 2, 5, mist=(214, 202, 176, 255))
    ridge(img, 144, 24, (96, 92, 92, 255), 3, 4, mist=(200, 188, 162, 255), mist_h=4)
    ink = (40, 36, 40, 255)
    # 절벽과 정자
    for y in range(100, 180):
        x1 = 70 - (180 - y) // 6
        rect(img, 0, y, x1, y, ink)
    rect(img, 34, 74, 36, 100, ink)
    rect(img, 58, 74, 60, 100, ink)
    rect(img, 30, 70, 64, 73, ink)
    for i in range(5):
        rect(img, 26 - i, 70 - i // 2, 68 + i, 70 - i // 2, ink)
    rect(img, 40, 62, 54, 68, ink)
    rect(img, 46, 57, 48, 61, ink)
    pine_silhouette(img, 72, 92, 6, ink)
    pine_silhouette(img, 292, 118, 5, (70, 66, 70, 255))
    rect(img, 0, 174, 319, 179, ink)
    save(scale(img, 2), "assets/backgrounds/title_bg.png")


def build_battle_bg():
    """640x360 전투 배경. 발 위치 그림자는 battle_scene.gd 배치(플레이어 180,226 / 적 460,214)와 맞춘다."""
    img = new(320, 180)
    gradient(img, (176, 178, 172), (224, 210, 180), 0, 92, bands=8)
    circle(img, 260, 30, 10, (200, 120, 90, 255))
    ridge(img, 64, 26, (170, 168, 160, 255), 4, 7, mist=(214, 204, 180, 255))
    ridge(img, 80, 20, (120, 120, 116, 255), 5, 5, mist=(206, 194, 168, 255), mist_h=3)
    rect(img, 0, 90, 319, 179, (150, 128, 98, 255))
    r = random.Random(3)
    for _ in range(220):
        x, y = r.randrange(0, 320), r.randrange(92, 180)
        px(img, x, y, (128, 108, 82, 255) if r.random() < 0.7 else (170, 148, 116, 255))
    rect(img, 0, 90, 319, 91, (96, 84, 66, 255))
    for x in (20, 300):  # 돌기둥
        rect(img, x, 50, x + 9, 92, (96, 92, 90, 255))
        rect(img, x, 50, x + 2, 92, (126, 122, 118, 255))
        rect(img, x - 2, 48, x + 11, 50, (70, 66, 66, 255))
    for x in range(40, 290, 46):  # 깃대
        rect(img, x, 70, x, 91, WOOD_D)
        rect(img, x + 1, 70, x + 6, 75, VERMILION)
    for cx, cy in ((90, 113), (230, 107)):
        ellipse(img, cx, cy, 26, 4, (118, 98, 74, 255))
    save(scale(img, 2), "assets/backgrounds/battle_training.png")


# ---------------------------------------------------------------- UI / 효과
def build_ui():
    for name, rot in (("up", 0), ("right", 270), ("down", 180), ("left", 90)):
        img = new(40, 40)
        rect(img, 2, 2, 37, 37, (24, 20, 22, 170))
        rect(img, 2, 2, 37, 2, (200, 170, 110, 120))
        for i in range(10):
            rect(img, 20 - i, 12 + i, 19 + i, 12 + i, (226, 216, 192, 230))
        img = img.rotate(rot)
        save(img, f"assets/ui/dpad_{name}.png")
    for name, col in (("a", (150, 40, 32)), ("b", (52, 50, 58))):
        img = new(52, 52)
        circle(img, 26, 26, 24, (24, 20, 22, 210))
        circle(img, 26, 26, 21, col + (230,))
        circle(img, 26, 26, 19, tuple(min(255, c + 20) for c in col) + (230,))
        save(img, f"assets/ui/btn_{name}.png")
    # 베기 효과 (전투)
    img = new(64, 64)
    for i in range(3):
        for t in range(48):
            x = 8 + t
            y = 52 - t + i * 5 - int(((t - 24) / 24) ** 2 * 6)
            a = int(255 * (1 - abs(t - 24) / 26))
            px(img, x, y, (255, 250, 236, a))
            px(img, x, y + 1, (230, 210, 170, a // 2))
    save(img, "assets/ui/slash.png")


def build_characters():
    for key, look in LOOKS.items():
        save(char_sheet(look), f"assets/characters/{key}.png")
    sc = draw_scarecrow()
    save(sc, "assets/characters/scarecrow.png")
    # 전투용 (3배)
    save(scale(sc, 3), "assets/enemies/scarecrow_battle.png")
    save(scale(draw_char(LOOKS["bandit"], "down", 0), 3), "assets/enemies/bandit_battle.png")
    save(scale(draw_char(LOOKS["doyun"], "left", 0).transpose(Image.FLIP_LEFT_RIGHT), 3),
         "assets/characters/doyun_battle.png")
    face = draw_char(LOOKS["doyun"], "down", 0).crop((6, 0, 26, 20))
    bg = new(128, 128, PAPER)
    circle(bg, 64, 64, 60, (178, 58, 42, 255))
    icon = face.resize((120, 120), Image.NEAREST)
    bg.alpha_composite(icon, (4, 10))
    save(bg, "icon.png")


# ---------------------------------------------------------------- 아이콘 (24x24) / 효과
def icon_base(bg=(54, 40, 34, 255)):
    img = new(24, 24)
    rect(img, 1, 1, 22, 22, bg)
    rect(img, 1, 1, 22, 1, (110, 86, 60, 255))
    return img


def icon_fist(img, ox=0, oy=0, c=SKIN):
    rect(img, 7 + ox, 8 + oy, 16 + ox, 16 + oy, c)
    for x in (9, 12, 15):
        px(img, x + ox, 8 + oy, shade(c, 0.75))
    rect(img, 7 + ox, 12 + oy, 9 + ox, 12 + oy, shade(c, 0.75))
    rect(img, 8 + ox, 17 + oy, 15 + ox, 19 + oy, (160, 36, 36, 255))


def build_icons():
    out = {}
    i = icon_base(); icon_fist(i); out["skill_fist"] = i
    i = icon_base(); icon_fist(i, -3, -2, shade(SKIN, 0.85)); icon_fist(i, 3, 2); out["skill_combo"] = i
    i = icon_base((90, 40, 30, 255))
    for r, c in ((9, (200, 120, 50, 255)), (6, (236, 190, 90, 255)), (3, (255, 236, 170, 255))):
        circle(i, 12, 12, r, c)
    out["skill_kihap"] = i
    i = icon_base((40, 56, 70, 255))
    for k, y in enumerate((7, 12, 17)):
        for x in range(4, 20):
            px(i, x, y + int(2 * __import__("math").sin((x + k * 3) / 2.5)), (200, 226, 230, 255))
    out["skill_breath"] = i
    i = icon_base((50, 50, 60, 255))
    rect(i, 6, 4, 17, 15, (150, 150, 160, 255))
    for y in range(16, 21):
        rect(i, 6 + (y - 15), y, 17 - (y - 15), y, (150, 150, 160, 255))
    rect(i, 8, 6, 15, 7, (200, 200, 210, 255))
    rect(i, 11, 8, 12, 16, (110, 110, 120, 255))
    out["skill_wall"] = i
    i = icon_base((40, 60, 52, 255))
    rect(i, 5, 14, 15, 17, (46, 58, 92, 255))
    rect(i, 15, 13, 19, 18, (46, 34, 30, 255))
    for k in range(3):
        rect(i, 3, 6 + k * 3, 12 - k * 2, 6 + k * 3, (210, 230, 220, 255))
    out["skill_kick"] = i
    i = icon_base((44, 60, 40, 255))
    for (x, y) in ((8, 14), (12, 9), (16, 13)):
        ellipse(i, x, y, 3, 5, (96, 150, 80, 255))
        rect(i, x, y - 4, x, y + 4, (60, 100, 54, 255))
    rect(i, 11, 15, 12, 20, (90, 70, 40, 255))
    out["item_herb"] = i
    i = icon_base((70, 40, 40, 255))
    circle(i, 12, 13, 6, (176, 54, 42, 255))
    circle(i, 10, 11, 2, (230, 140, 110, 255))
    out["item_pill"] = i
    i = icon_base((60, 50, 40, 255))
    rect(i, 5, 6, 18, 18, PAPER)
    for y in (9, 12, 15):
        rect(i, 7, y, 15, y, (60, 50, 50, 255))
    rect(i, 16, 13, 18, 18, (60, 50, 40, 255))
    out["item_scroll"] = i
    for key, c in (("fish_crucian", (130, 130, 110, 255)), ("fish_carp", (190, 120, 70, 255)), ("fish_gold", (232, 190, 70, 255))):
        i = icon_base((40, 64, 72, 255))
        ellipse(i, 11, 12, 7, 4, c)
        for y in range(8, 17):
            d = abs(y - 12)
            rect(i, 18, y, 18 + (4 - d) // 1 if d < 4 else 18, y, c)
        px(i, 7, 11, EYE)
        out[key] = i
    i = icon_base((60, 44, 34, 255)); icon_fist(i, 0, 0, (226, 216, 192, 255)); out["gear_fist"] = i
    i = icon_base((40, 44, 60, 255))
    rect(i, 6, 5, 17, 19, (46, 58, 92, 255))
    rect(i, 3, 6, 6, 13, (32, 40, 66, 255))
    rect(i, 17, 6, 20, 13, (32, 40, 66, 255))
    for k in range(5):
        px(i, 9 + k, 5 + k, (214, 206, 186, 255))
    rect(i, 6, 13, 17, 14, (150, 40, 40, 255))
    out["gear_robe"] = i
    i = icon_base((44, 50, 66, 255))
    for y in range(5, 20):
        hw = 7 if y < 14 else 7 - (y - 13)
        rect(i, 12 - hw, y, 11 + hw, y, (176, 186, 200, 255))
    rect(i, 11, 6, 12, 17, (110, 120, 136, 255))
    out["card_block"] = i
    i = icon_base((70, 50, 40, 255))
    rect(i, 4, 14, 12, 17, (64, 62, 72, 255)); rect(i, 12, 13, 17, 18, (36, 30, 32, 255))
    for k in range(3):
        rect(i, 14 + k, 6 + k * 3, 18 + k, 6 + k * 3, (230, 220, 200, 255))
    out["card_trip"] = i
    i = icon_base((50, 46, 70, 255))
    circle(i, 12, 12, 7, (200, 190, 240, 255)); circle(i, 12, 12, 4, (120, 100, 200, 255)); circle(i, 12, 12, 1, (255, 255, 255, 255))
    out["card_focus"] = i
    i = icon_base((60, 44, 40, 255))
    for y in range(5, 20):
        hw = 6 if y < 14 else 6 - (y - 13)
        rect(i, 12 - hw, y, 11 + hw, y, (176, 120, 90, 255))
    thick = [(6, 6), (9, 9), (12, 12), (15, 15), (18, 18)]
    for x, y in thick:
        rect(i, x, y, x + 1, y + 1, (255, 230, 160, 255))
    out["card_counter"] = i
    i = icon_base((60, 44, 34, 255))
    rect(i, 6, 6, 15, 18, SKIN); rect(i, 6, 6, 15, 7, shade(SKIN, 0.8))
    for x in (8, 10, 12, 14):
        rect(i, x, 3, x, 6, SKIN)
    rect(i, 15, 10, 19, 12, SKIN)
    rect(i, 4, 19, 17, 20, (150, 150, 160, 255))
    out["card_palm"] = i
    i = icon_base((80, 30, 26, 255))
    for k in range(3):
        rect(i, 5 + k * 5, 18 - k * 4, 8 + k * 5, 20, (236, 120, 70, 255))
    rect(i, 15, 4, 18, 8, (255, 220, 120, 255))
    out["card_spirit"] = i
    i = icon_base((60, 40, 44, 255))
    circle(i, 12, 12, 7, (176, 54, 42, 255)); circle(i, 12, 12, 4, (240, 226, 200, 255)); circle(i, 12, 12, 1, (176, 54, 42, 255))
    rect(i, 3, 11, 9, 12, (230, 230, 240, 255))
    out["card_point"] = i
    # 적 의도
    i = new(24, 24)
    for k in range(10):
        rect(i, 5 + k, 18 - k, 7 + k, 19 - k, (230, 230, 240, 255))
    rect(i, 3, 15, 10, 16, (150, 110, 60, 255)); rect(i, 4, 17, 6, 21, (110, 70, 40, 255))
    out["intent_attack"] = outline(i)
    i = new(24, 24)
    for y in range(3, 21):
        hw = 8 if y < 13 else 8 - (y - 12)
        rect(i, 12 - hw, y, 11 + hw, y, (120, 160, 220, 255))
    rect(i, 11, 4, 12, 18, (80, 110, 170, 255))
    out["intent_block"] = outline(i)
    i = new(24, 24)
    for y in range(4, 14):
        rect(i, 12 - (y - 4), y, 11 + (y - 4), y, (230, 90, 70, 255))
    rect(i, 9, 14, 14, 20, (230, 90, 70, 255))
    out["intent_buff"] = outline(i)
    i = new(24, 24)
    circle(i, 12, 12, 9, (200, 200, 190, 255))
    rect(i, 10, 6, 14, 7, (60, 50, 50, 255)); rect(i, 14, 8, 15, 10, (60, 50, 50, 255)); rect(i, 12, 11, 13, 13, (60, 50, 50, 255)); rect(i, 12, 16, 13, 17, (60, 50, 50, 255))
    out["intent_idle"] = outline(i)
    out["qi"] = icon_base((40, 40, 70, 255))
    circle(out["qi"], 12, 12, 7, (110, 140, 220, 255))
    circle(out["qi"], 12, 12, 4, (200, 220, 255, 255))
    out["gold"] = icon_base((60, 50, 30, 255))
    circle(out["gold"], 12, 12, 7, (210, 170, 70, 255))
    rect(out["gold"], 10, 10, 13, 13, (60, 50, 30, 255))
    for k, img in out.items():
        save(img, f"assets/ui/icons/{k}.png")


def build_effects():
    g = new(64, 64)
    for y in range(64):
        for x in range(64):
            d = ((x - 31.5) ** 2 + (y - 31.5) ** 2) ** 0.5 / 32
            if d < 1:
                g.putpixel((x, y), (255, 210, 140, int(140 * (1 - d) ** 2)))
    save(g, "assets/ui/glow.png")
    leaf = new(6, 4)
    rect(leaf, 1, 1, 4, 2, (196, 120, 70, 255))
    px(leaf, 0, 2, (160, 90, 50, 255))
    px(leaf, 5, 1, (220, 150, 90, 255))
    save(leaf, "assets/ui/leaf.png")
    mist = new(128, 32)
    for y in range(32):
        for x in range(128):
            a = int(90 * (1 - abs(y - 16) / 16) * (0.6 + 0.4 * ((x * 7 + y * 3) % 11) / 11))
            mist.putpixel((x, y), (236, 230, 216, max(0, a)))
    save(mist, "assets/ui/mist.png")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import art_chars  # v4 캐릭터 (개성 있는 SD + 표정 + 전투 자세)
    build_tileset()
    art_chars.build_all()
    art_chars.build_fx()
    build_title_bg()
    build_battle_bg()
    build_ui()
    build_icons()
    build_effects()

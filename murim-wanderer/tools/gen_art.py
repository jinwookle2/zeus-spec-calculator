#!/usr/bin/env python3
"""무림유랑기 임시 픽셀아트 생성기.

외부 에셋 없이 모든 프로토타입 그래픽을 코드로 생성한다.
결과물은 전부 이 프로젝트의 독창적 창작물이며 상업적 이용에 제한이 없다.

사용법 (프로젝트 루트에서):
    python3 tools/gen_art.py
필요 패키지: Pillow
"""
from __future__ import annotations

import os
import random
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = 32  # 타일 크기

# ---------------------------------------------------------------- 팔레트
OUT = (34, 26, 38, 255)
CLEAR = (0, 0, 0, 0)
SKIN = (248, 208, 164, 255)
SKIN_D = (218, 164, 124, 255)
BLUSH = (240, 150, 130, 255)
EYE = (36, 28, 40, 255)
WHITE = (250, 248, 240, 255)

GRASS = (104, 174, 76, 255)
GRASS_D = (76, 142, 60, 255)
GRASS_L = (140, 200, 94, 255)
DIRT = (204, 168, 112, 255)
DIRT_D = (172, 134, 86, 255)
DIRT_L = (222, 192, 140, 255)
STONE = (168, 164, 158, 255)
STONE_D = (124, 120, 118, 255)
STONE_L = (200, 196, 188, 255)
WOOD = (150, 96, 56, 255)
WOOD_D = (104, 64, 40, 255)
WOOD_L = (186, 128, 76, 255)
LEAF = (60, 140, 70, 255)
LEAF_D = (36, 100, 56, 255)
LEAF_L = (100, 180, 84, 255)
WATER = (70, 140, 210, 255)
WATER_D = (50, 106, 180, 255)
WATER_L = (150, 200, 240, 255)
PLASTER = (238, 224, 196, 255)
PLASTER_D = (210, 192, 160, 255)
SAND = (226, 202, 150, 255)
SAND_D = (200, 172, 120, 255)

ROOFS = {
    "red": ((196, 74, 60, 255), (150, 50, 46, 255), (226, 112, 90, 255)),
    "blue": ((70, 86, 140, 255), (48, 58, 100, 255), (106, 124, 180, 255)),
    "green": ((60, 132, 100, 255), (40, 96, 74, 255), (96, 170, 130, 255)),
}


def new(w, h, color=CLEAR):
    return Image.new("RGBA", (w, h), color)


def rect(img, x0, y0, x1, y1, c):
    """x0..x1, y0..y1 포함 사각형."""
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


def outline(img, color=OUT):
    """불투명 픽셀 주변의 투명 픽셀에 외곽선을 그린다."""
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


# ---------------------------------------------------------------- 캐릭터
class Look:
    def __init__(self, **kw):
        self.hair = (44, 34, 44, 255)
        self.hair_l = (84, 66, 84, 255)
        self.style = "topknot"  # topknot | bun | bald | hat | bandana
        self.band = None  # 머리띠 색
        self.top = (240, 236, 222, 255)
        self.top_d = (196, 190, 176, 255)
        self.belt = (60, 90, 170, 255)
        self.pants = (60, 90, 170, 255)
        self.pants_d = (44, 66, 130, 255)
        self.shoes = (90, 60, 44, 255)
        self.beard = None  # 수염 색
        self.mustache = None
        self.brows = None  # 눈썹 색 (None 이면 머리색)
        self.wide = 0  # 몸통 추가 폭
        self.skirt = False
        self.hat = (40, 34, 40, 255)
        self.eyepatch = False
        self.__dict__.update(kw)


def draw_char(look: Look, facing: str, frame: int) -> Image.Image:
    """facing: down/up/left. frame: 0=정지, 1/2=걷기."""
    img = new(T, T)
    bob = 1 if frame in (1, 2) else 0
    w = look.wide
    side = facing == "left"

    # 다리/신발
    ly = 24
    if look.skirt:
        rect(img, 9 - w, 23, 22 + w, 28, look.pants)
        rect(img, 9 - w, 28, 22 + w, 28, look.pants_d)
        lf = (11, 14) if not side else (12, 15)
        rf = (17, 20) if not side else (16, 19)
        l_off = -1 if frame == 1 else 0
        r_off = -1 if frame == 2 else 0
        rect(img, lf[0], 29 + l_off, lf[1], 30 + l_off, look.shoes)
        rect(img, rf[0], 29 + r_off, rf[1], 30 + r_off, look.shoes)
    elif side:
        # 옆모습: 다리가 앞뒤로 벌어짐
        if frame == 0:
            rect(img, 13, ly, 18, 28, look.pants)
            rect(img, 13, 29, 19, 30, look.shoes)
        else:
            rect(img, 11, ly, 15, 28, look.pants_d)
            rect(img, 16, ly, 20, 28, look.pants)
            rect(img, 9, 29, 14, 30, look.shoes)
            rect(img, 16, 29, 21, 30, look.shoes)
    else:
        l_off = -1 if frame == 1 else 0
        r_off = -1 if frame == 2 else 0
        rect(img, 10 - w, ly, 15, 28 + l_off, look.pants)
        rect(img, 16, ly, 21 + w, 28 + r_off, look.pants)
        rect(img, 15, 26, 16, 28, CLEAR)
        rect(img, 15, ly, 16, 25, look.pants_d)
        rect(img, 10 - w, 29 + l_off, 14, 30 + l_off, look.shoes)
        rect(img, 17, 29 + r_off, 21 + w, 30 + r_off, look.shoes)

    by = -bob
    # 몸통
    if side:
        rect(img, 11 - w // 2, 15 + by, 20 + w // 2, 23 + by, look.top)
        rect(img, 11 - w // 2, 15 + by, 12 - w // 2, 23 + by, look.top_d)
        rect(img, 11 - w // 2, 22 + by, 20 + w // 2, 23 + by, look.belt)
        # 팔 (앞으로 흔들기)
        sw = {0: 0, 1: 2, 2: -2}[frame]
        rect(img, 14 + sw, 16 + by, 17 + sw, 21 + by, look.top_d)
        rect(img, 14 + sw, 22 + by, 16 + sw, 23 + by, SKIN)
    else:
        rect(img, 9 - w, 15 + by, 22 + w, 23 + by, look.top)
        rect(img, 9 - w, 15 + by, 10 - w, 23 + by, look.top_d)
        rect(img, 21 + w, 15 + by, 22 + w, 23 + by, look.top_d)
        if facing == "down":
            # 옷깃 (V)
            for i in range(4):
                px(img, 13 + i, 15 + i + by, look.top_d)
                px(img, 18 - i, 15 + i + by, look.top_d)
        else:
            rect(img, 15, 16 + by, 16, 21 + by, look.top_d)
        rect(img, 9 - w, 22 + by, 22 + w, 23 + by, look.belt)
        # 팔
        la = {0: 0, 1: -1, 2: 1}[frame]
        rect(img, 7 - w, 16 + by + la, 8 - w, 21 + by + la, look.top_d)
        rect(img, 23 + w, 16 + by - la, 24 + w, 21 + by - la, look.top_d)
        rect(img, 7 - w, 22 + by + la, 8 - w, 23 + by + la, SKIN)
        rect(img, 23 + w, 22 + by - la, 24 + w, 23 + by - la, SKIN)

    # 머리
    hx0, hx1 = (10, 21)
    hy0, hy1 = 4 + by, 14 + by
    rect(img, hx0, hy0, hx1, hy1, SKIN)
    for cx, cy in ((hx0, hy0), (hx1, hy0), (hx0, hy1), (hx1, hy1)):
        px(img, cx, cy, CLEAR)
    rect(img, hx0 + 1, hy1, hx1 - 1, hy1, SKIN_D)

    hair, hair_l = look.hair, look.hair_l
    if look.style != "bald":
        if facing == "up":
            rect(img, hx0, hy0, hx1, hy1 - 1, hair)
            rect(img, hx0 + 2, hy0 + 1, hx0 + 5, hy0 + 2, hair_l)
        elif side:
            rect(img, hx0, hy0, hx1, hy0 + 3, hair)
            rect(img, hx0 + 5, hy0, hx1, hy0 + 8, hair)
            rect(img, hx0 + 1, hy0, hx0 + 4, hy0 + 1, hair_l)
        else:
            rect(img, hx0, hy0, hx1, hy0 + 3, hair)
            rect(img, hx0, hy0 + 4, hx0 + 1, hy0 + 7, hair)
            rect(img, hx1 - 1, hy0 + 4, hx1, hy0 + 7, hair)
            rect(img, hx0 + 2, hy0, hx0 + 6, hy0 + 1, hair_l)
    else:
        rect(img, hx0 + 2, hy0, hx0 + 5, hy0 + 1, (255, 230, 196, 255))

    if look.style == "topknot":
        tx = 14 if not side else 17
        rect(img, tx, hy0 - 3, tx + 3, hy0 - 1, hair)
        px(img, tx + 1, hy0 - 3, hair_l)
    elif look.style == "bun":
        bx = 13 if not side else 17
        rect(img, bx, hy0 - 3, bx + 5, hy0, hair)
        rect(img, bx + 1, hy0 - 2, bx + 2, hy0 - 2, hair_l)
        rect(img, bx + 2, hy0 - 1, bx + 3, hy0 - 1, (220, 180, 60, 255))  # 비녀
    elif look.style == "hat":
        rect(img, hx0 + 2, hy0 - 4, hx1 - 2, hy0 + 1, look.hat)
        rect(img, hx0 - 4, hy0 + 2, hx1 + 4, hy0 + 2, look.hat)
        rect(img, hx0 + 3, hy0 - 3, hx0 + 5, hy0 - 3, (90, 80, 90, 255))
    elif look.style == "bandana":
        rect(img, hx0, hy0, hx1, hy0 + 3, look.hat)
        rect(img, hx0 + 2, hy0 + 1, hx0 + 3, hy0 + 1, (230, 220, 200, 255))
        if facing != "down":
            kx = hx0 - 2 if side else 15
            rect(img, kx + (8 if side else 0), hy0 + 3, kx + 10 if side else kx + 2, hy0 + 5, look.hat)

    if look.band:
        rect(img, hx0, hy0 + 3, hx1, hy0 + 3, look.band)
        if facing == "up":
            rect(img, 15, hy0 + 4, 15, hy0 + 7, look.band)
            rect(img, 17, hy0 + 4, 17, hy0 + 8, look.band)
        elif side:
            rect(img, hx0, hy0 + 3, hx0 + 4, hy0 + 3, hair)
            px(img, hx1 + 1, hy0 + 4, look.band)
            px(img, hx1 + 2, hy0 + 5, look.band)
            px(img, hx1 + 2, hy0 + 6, look.band)

    # 얼굴
    brow = look.brows or hair
    if facing == "down":
        ey = hy0 + 6
        rect(img, 13, ey, 13, ey + 1, EYE)
        rect(img, 18, ey, 18, ey + 1, EYE)
        rect(img, 12, ey - 1, 14, ey - 1, brow)
        rect(img, 17, ey - 1, 19, ey - 1, brow)
        px(img, 12, ey + 2, BLUSH)
        px(img, 19, ey + 2, BLUSH)
        rect(img, 15, ey + 3, 16, ey + 3, (190, 100, 90, 255))
        if look.eyepatch:
            rect(img, 17, ey - 1, 19, ey + 1, EYE)
            rect(img, hx0, ey - 2, hx1, ey - 2, EYE)
    elif side:
        ey = hy0 + 6
        rect(img, 11, ey, 11, ey + 1, EYE)
        rect(img, 10, ey - 1, 12, ey - 1, brow)
        px(img, 12, ey + 2, BLUSH)
        px(img, hx0 - 1, ey + 1, SKIN)  # 코
        rect(img, 11, ey + 3, 12, ey + 3, (190, 100, 90, 255))
    if look.mustache and facing != "up":
        if side:
            rect(img, 9, hy0 + 8, 13, hy0 + 8, look.mustache)
        else:
            rect(img, 12, hy0 + 8, 19, hy0 + 8, look.mustache)
            px(img, 11, hy0 + 9, look.mustache)
            px(img, 20, hy0 + 9, look.mustache)
    if look.beard and facing != "up":
        if side:
            rect(img, 9, hy0 + 9, 14, hy1 + 5, look.beard)
            rect(img, 10, hy1 + 6, 13, hy1 + 7, look.beard)
        else:
            rect(img, 12, hy0 + 9, 19, hy1 + 5, look.beard)
            rect(img, 13, hy1 + 6, 18, hy1 + 7, look.beard)
            rect(img, 14, hy1 + 8, 17, hy1 + 8, look.beard)
            rect(img, 15, hy0 + 9, 16, hy0 + 9, (190, 100, 90, 255))

    return outline(img)


def char_sheet(look: Look) -> Image.Image:
    """4행(하/좌/우/상) x 3열(정지/걸음1/걸음2)."""
    sheet = new(T * 3, T * 4)
    for row, facing in enumerate(["down", "left", "right", "up"]):
        for f in range(3):
            if facing == "right":
                fr = draw_char(look, "left", f).transpose(Image.FLIP_LEFT_RIGHT)
            else:
                fr = draw_char(look, facing, f)
            sheet.paste(fr, (f * T, row * T), fr)
    return sheet


LOOKS = {
    "doyun": Look(band=(214, 52, 52, 255)),
    "master": Look(
        hair=(214, 214, 220, 255), hair_l=(250, 250, 255, 255), brows=(250, 250, 255, 255),
        beard=(238, 238, 244, 255), top=(120, 132, 160, 255), top_d=(90, 100, 130, 255),
        belt=(50, 44, 60, 255), pants=(80, 86, 110, 255), pants_d=(60, 66, 88, 255),
    ),
    "villager": Look(
        style="bun", hair=(74, 48, 40, 255), hair_l=(110, 74, 60, 255), skirt=True,
        top=(250, 222, 110, 255), top_d=(220, 186, 80, 255), belt=(200, 60, 80, 255),
        pants=(200, 64, 86, 255), pants_d=(160, 44, 66, 255), shoes=(240, 236, 230, 255),
    ),
    "merchant": Look(
        style="hat", wide=2, mustache=(44, 34, 44, 255), top=(110, 160, 96, 255),
        top_d=(80, 124, 70, 255), belt=(170, 120, 50, 255), pants=(130, 96, 70, 255),
        pants_d=(100, 70, 50, 255),
    ),
    "bandit": Look(
        style="bandana", hat=(150, 40, 40, 255), wide=1, eyepatch=True,
        mustache=(54, 40, 40, 255), top=(140, 104, 70, 255), top_d=(104, 74, 50, 255),
        belt=(60, 50, 40, 255), pants=(70, 70, 76, 255), pants_d=(50, 50, 56, 255),
    ),
}


def draw_scarecrow() -> Image.Image:
    img = new(T, T)
    rect(img, 15, 12, 16, 30, WOOD)  # 기둥
    rect(img, 6, 15, 25, 16, WOOD)  # 가로대
    rect(img, 10, 14, 21, 24, (176, 90, 70, 255))  # 셔츠
    rect(img, 13, 18, 15, 20, (90, 120, 170, 255))  # 덧댄 천
    rect(img, 10, 23, 21, 24, (130, 70, 56, 255))
    for x in (5, 26):
        rect(img, x, 14, x, 17, (230, 200, 90, 255))  # 지푸라기 손
    rect(img, 11, 4, 20, 13, (226, 204, 150, 255))  # 자루 머리
    rect(img, 13, 7, 14, 8, EYE)
    px(img, 18, 7, EYE)
    px(img, 17, 8, EYE)
    px(img, 19, 8, EYE)  # X 눈
    px(img, 18, 9, EYE)
    rect(img, 13, 11, 18, 11, (150, 80, 70, 255))  # 꿰맨 입
    for x in (14, 16, 18):
        px(img, x, 10, (150, 80, 70, 255))
    rect(img, 8, 3, 23, 4, (220, 180, 80, 255))  # 밀짚모자
    rect(img, 11, 0, 20, 3, (230, 196, 96, 255))
    rect(img, 11, 2, 20, 2, (196, 60, 60, 255))
    return outline(img)


# ---------------------------------------------------------------- 타일
rng = random.Random(42)


def grass_base(seed=0):
    r = random.Random(seed)
    img = new(T, T, GRASS)
    for _ in range(18):
        x, y = r.randrange(1, 31), r.randrange(2, 31)
        c = GRASS_D if r.random() < 0.6 else GRASS_L
        px(img, x, y, c)
        px(img, x - 1, y - 1, c)
        px(img, x + 1, y - 1, c)
    return img


def tile_flowers():
    img = grass_base(1)
    r = random.Random(7)
    for c in ((236, 90, 90, 255), (250, 220, 90, 255), (250, 250, 250, 255), (236, 90, 90, 255)):
        x, y = r.randrange(3, 29), r.randrange(3, 29)
        px(img, x, y, (250, 236, 120, 255))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            px(img, x + dx, y + dy, c)
    return img


def tile_dirt(seed=3):
    r = random.Random(seed)
    img = new(T, T, DIRT)
    for _ in range(14):
        x, y = r.randrange(0, 31), r.randrange(0, 31)
        c = DIRT_D if r.random() < 0.6 else DIRT_L
        rect(img, x, y, x + 1, y, c)
    return img


def tile_sand():
    r = random.Random(9)
    img = new(T, T, SAND)
    for _ in range(16):
        x, y = r.randrange(0, 31), r.randrange(0, 31)
        px(img, x, y, SAND_D if r.random() < 0.7 else (240, 222, 180, 255))
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
    img = grass_base(4)
    top = new(T, T)
    rect(top, 13, 22, 18, 30, WOOD)
    rect(top, 13, 22, 14, 30, WOOD_D)
    circle(top, 16, 12, 12, LEAF_D)
    circle(top, 15, 11, 10, LEAF)
    circle(top, 12, 8, 4, LEAF_L)
    r = random.Random(5)
    for _ in range(10):
        x, y = r.randrange(6, 26), r.randrange(4, 20)
        if top.getpixel((x, y))[3]:
            px(top, x, y, LEAF_D)
    outline(top)
    # 그림자
    rect(img, 9, 29, 23, 30, GRASS_D)
    img.alpha_composite(top)
    return img


def tile_bush():
    img = grass_base(6)
    top = new(T, T)
    circle(top, 16, 19, 10, LEAF_D)
    circle(top, 15, 18, 8, LEAF)
    circle(top, 12, 15, 3, LEAF_L)
    px(top, 20, 14, (236, 90, 90, 255))
    px(top, 10, 21, (236, 90, 90, 255))
    outline(top)
    img.alpha_composite(top)
    return img


def tile_rock():
    img = grass_base(8)
    top = new(T, T)
    circle(top, 16, 18, 10, STONE_D)
    circle(top, 15, 17, 8, STONE)
    circle(top, 12, 14, 3, STONE_L)
    rect(top, 6, 27, 26, 31, CLEAR)
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
    for _ in range(5):
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
        rect(img, 10, 10, 21, 19, (250, 236, 200, 255))
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
    px(img, 14, 20, (230, 200, 90, 255))
    px(img, 17, 20, (230, 200, 90, 255))
    return img


def tile_roof(color, eave=False):
    base, dark, light = ROOFS[color]
    img = new(T, T, base)
    for y0 in range(0, 32, 8):
        rect(img, 0, y0 + 6, 31, y0 + 7, dark)
        for x0 in range(0, 32, 8):
            rect(img, x0 + 1, y0 + 1, x0 + 3, y0 + 1, light)
            rect(img, x0 + 7, y0, x0 + 7, y0 + 7, dark)
    if eave:
        rect(img, 0, 22, 31, 25, dark)
        rect(img, 0, 22, 31, 22, light)
        rect(img, 0, 26, 31, 31, (60, 44, 40, 255))  # 처마 그늘
        for x in range(1, 32, 6):
            rect(img, x, 26, x + 2, 28, WOOD_D)
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
    circle(top, 16, 20, 9, (140, 80, 60, 255))
    circle(top, 14, 18, 3, (180, 110, 80, 255))
    rect(top, 11, 8, 20, 11, (120, 66, 50, 255))
    rect(top, 12, 8, 19, 8, (70, 40, 34, 255))
    rect(top, 9, 18, 23, 18, (110, 60, 46, 255))
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
    rect(top, 14, 7, 17, 9, (196, 60, 60, 255))
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
    rect(top, 11, 8, 20, 17, (230, 120, 60, 255))
    rect(top, 13, 10, 18, 15, (255, 220, 120, 255))
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


# ---------------------------------------------------------------- 배경
def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def sky(img, top, bottom, bands=10, height=None):
    h = height or img.height
    for y in range(h):
        t = int(y / h * bands) / bands
        rect(img, 0, y, img.width - 1, y, lerp(top, bottom, t))


def mountains(img, base_y, amp, color, seed, step=4):
    r = random.Random(seed)
    w = img.width
    hgt = base_y
    target = base_y
    for x in range(0, w):
        if x % step == 0:
            target = base_y - r.randint(0, amp)
        hgt += (target > hgt) - (target < hgt)
        rect(img, x, hgt, x, img.height - 1, color)


def build_title_bg():
    img = new(320, 180)
    sky(img, (250, 180, 110), (180, 90, 130), bands=12, height=120)
    rect(img, 0, 120, 319, 179, (90, 60, 100, 255))
    circle(img, 236, 70, 22, (255, 226, 150, 255))
    circle(img, 236, 70, 18, (255, 244, 200, 255))
    for y, x0, x1 in ((40, 20, 90), (44, 30, 110), (60, 160, 210), (30, 250, 300)):
        rect(img, x0, y, x1, y + 1, (255, 214, 180, 255))
    mountains(img, 110, 40, (150, 90, 140, 255), 1, 5)
    mountains(img, 130, 34, (110, 66, 116, 255), 2, 4)
    mountains(img, 152, 22, (70, 44, 84, 255), 3, 3)
    # 절벽 위 정자 실루엣
    sil = (44, 28, 56, 255)
    rect(img, 30, 112, 70, 179, sil)
    rect(img, 36, 90, 38, 112, sil)
    rect(img, 62, 90, 64, 112, sil)
    rect(img, 30, 84, 70, 89, sil)
    for i in range(6):
        rect(img, 26 - i, 84 + i // 2, 74 + i, 84 + i // 2, sil)
    rect(img, 40, 76, 60, 84, sil)
    rect(img, 48, 70, 52, 76, sil)
    # 소나무
    for tx in (90, 280, 300):
        rect(img, tx, 120, tx + 2, 179, sil)
        for i, wdt in enumerate((14, 18, 12)):
            rect(img, tx + 1 - wdt // 2, 120 + i * 10, tx + 1 + wdt // 2, 124 + i * 10, sil)
    rect(img, 0, 168, 319, 179, (36, 22, 46, 255))
    save(scale(img, 2), "assets/backgrounds/title_bg.png")


def build_battle_bg():
    """640x360 전투 배경. 지면 그림자 위치는 battle_scene.gd 의 배치와 맞춘다."""
    img = new(320, 180)
    sky(img, (120, 180, 240), (200, 230, 250), bands=8, height=90)
    for y, x0, x1 in ((18, 30, 80), (22, 40, 100), (34, 200, 260), (12, 230, 300)):
        rect(img, x0, y, x1, y + 3, (250, 252, 255, 255))
    mountains(img, 72, 30, (140, 170, 200, 255), 4, 5)
    mountains(img, 86, 20, (96, 140, 120, 255), 5, 4)
    rect(img, 0, 90, 319, 179, SAND)
    r = random.Random(3)
    for _ in range(160):
        x, y = r.randrange(0, 320), r.randrange(92, 180)
        px(img, x, y, SAND_D)
    rect(img, 0, 90, 319, 92, GRASS_D)
    for x in range(0, 320, 40):
        rect(img, x + 6, 76, x + 9, 92, WOOD)
        rect(img, x, 80, x + 40, 81, WOOD_L)
    for cx, cy in ((90, 112), (230, 106)):
        for y in range(cy - 5, cy + 6):
            for x in range(cx - 30, cx + 31):
                if ((x - cx) / 30) ** 2 + ((y - cy) / 5) ** 2 <= 1:
                    px(img, x, y, SAND_D)
    save(scale(img, 2), "assets/backgrounds/battle_training.png")


# ---------------------------------------------------------------- UI
def build_ui():
    # 방향키
    for name, rot in (("up", 0), ("right", 270), ("down", 180), ("left", 90)):
        img = new(40, 40)
        rect(img, 2, 2, 37, 37, (40, 34, 56, 170))
        rect(img, 2, 2, 37, 3, (255, 255, 255, 60))
        for i in range(10):
            rect(img, 20 - i, 12 + i, 19 + i, 12 + i, (250, 236, 200, 230))
        img = img.rotate(rot)
        save(img, f"assets/ui/dpad_{name}.png")
    for name, col in (("a", (200, 70, 60)), ("b", (70, 90, 160))):
        img = new(52, 52)
        circle(img, 26, 26, 24, (30, 24, 40, 200))
        circle(img, 26, 26, 21, col + (220,))
        circle(img, 22, 20, 6, tuple(min(255, c + 50) for c in col) + (220,))
        save(img, f"assets/ui/btn_{name}.png")


def build_characters():
    for key, look in LOOKS.items():
        save(char_sheet(look), f"assets/characters/{key}.png")
    sc = draw_scarecrow()
    save(sc, "assets/characters/scarecrow.png")
    # 전투용 (2배)
    save(scale(sc, 2), "assets/enemies/scarecrow_battle.png")
    save(scale(draw_char(LOOKS["bandit"], "down", 0), 2), "assets/enemies/bandit_battle.png")
    save(scale(draw_char(LOOKS["doyun"], "left", 0).transpose(Image.FLIP_LEFT_RIGHT), 2),
         "assets/characters/doyun_battle.png")
    icon = scale(draw_char(LOOKS["doyun"], "down", 0).crop((4, 0, 28, 24)), 5)
    bg = new(128, 128, (250, 196, 120, 255))
    bg.alpha_composite(icon.resize((120, 120), Image.NEAREST), (4, 6))
    save(bg, "icon.png")


if __name__ == "__main__":
    build_tileset()
    build_characters()
    build_title_bg()
    build_battle_bg()
    build_ui()

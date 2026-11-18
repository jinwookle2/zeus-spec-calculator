class_name SpriteFramesBuilder
extends RefCounted
## 4방향 x 3프레임 캐릭터 시트(행: 하/좌/우/상, 열: 정지/걸음1/걸음2)로 SpriteFrames 생성.

const DIRS := ["down", "left", "right", "up"]
const CELL := 32

static var _cache: Dictionary = {}


static func from_sheet(path: String) -> SpriteFrames:
	if _cache.has(path):
		return _cache[path]
	var tex: Texture2D = load(path)
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	var single := tex.get_height() <= CELL
	for row in DIRS.size():
		var dir: String = DIRS[row]
		var r := 0 if single else row
		frames.add_animation("idle_" + dir)
		frames.set_animation_loop("idle_" + dir, true)
		frames.add_frame("idle_" + dir, _atlas(tex, 0, r))
		frames.add_animation("walk_" + dir)
		frames.set_animation_speed("walk_" + dir, 8.0)
		frames.set_animation_loop("walk_" + dir, true)
		if single:
			frames.add_frame("walk_" + dir, _atlas(tex, 0, 0))
		else:
			for c in [1, 0, 2, 0]:
				frames.add_frame("walk_" + dir, _atlas(tex, c, r))
	_cache[path] = frames
	return frames


static func _atlas(tex: Texture2D, col: int, row: int) -> AtlasTexture:
	var a := AtlasTexture.new()
	a.atlas = tex
	a.region = Rect2(col * CELL, row * CELL, CELL, CELL)
	return a


static func dir_name(v: Vector2) -> String:
	if absf(v.x) > absf(v.y):
		return "right" if v.x > 0 else "left"
	return "down" if v.y > 0 else "up"


static func dir_vector(dir: String) -> Vector2:
	match dir:
		"up":
			return Vector2.UP
		"left":
			return Vector2.LEFT
		"right":
			return Vector2.RIGHT
	return Vector2.DOWN

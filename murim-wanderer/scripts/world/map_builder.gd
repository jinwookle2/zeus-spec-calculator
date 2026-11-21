class_name MapBuilder
extends RefCounted
## data/maps/*.json 의 문자 지도를 TileMapLayer 로 변환한다.
## 타일 정의(문자→타일셋 인덱스, 충돌 여부)는 data/maps/tiles.json.

const TILE := 32
const SOURCE_ID := 0

static var _tileset_cache: TileSet


static func get_tileset() -> TileSet:
	if _tileset_cache:
		return _tileset_cache
	var def: Dictionary = DataDB.tiles
	var ts := TileSet.new()
	ts.tile_size = Vector2i(TILE, TILE)
	ts.add_physics_layer()
	ts.set_physics_layer_collision_layer(0, 1)
	ts.set_physics_layer_collision_mask(0, 0)
	var src := TileSetAtlasSource.new()
	src.texture = load(def.get("tileset", ""))
	src.texture_region_size = Vector2i(TILE, TILE)
	ts.add_source(src, SOURCE_ID)
	var half := TILE / 2.0
	var square := PackedVector2Array([Vector2(-half, -half), Vector2(half, -half), Vector2(half, half), Vector2(-half, half)])
	var legend: Dictionary = def.get("legend", {})
	for ch in legend:
		var coords := atlas_coords(int(legend[ch]["index"]))
		if not src.has_tile(coords):
			src.create_tile(coords)
		if bool(legend[ch].get("solid", false)):
			var td := src.get_tile_data(coords, 0)
			if td.get_collision_polygons_count(0) == 0:
				td.add_collision_polygon(0)
				td.set_collision_polygon_points(0, 0, square)
	_tileset_cache = ts
	return ts


static func atlas_coords(index: int) -> Vector2i:
	var cols := int(DataDB.tiles.get("columns", 8))
	return Vector2i(index % cols, index / cols)


static func build_layer(map_data: Dictionary) -> TileMapLayer:
	var layer := TileMapLayer.new()
	layer.name = "Ground"
	layer.tile_set = get_tileset()
	var legend: Dictionary = DataDB.tiles.get("legend", {})
	var rows: Array = map_data.get("tiles", [])
	for y in rows.size():
		var row: String = rows[y]
		for x in row.length():
			var ch := row[x]
			if not legend.has(ch):
				push_warning("알 수 없는 타일 문자 '%s' (%d,%d)" % [ch, x, y])
				ch = "."
			layer.set_cell(Vector2i(x, y), SOURCE_ID, atlas_coords(int(legend[ch]["index"])))
	return layer


static func is_solid(map_data: Dictionary, tile: Vector2i) -> bool:
	var rows: Array = map_data.get("tiles", [])
	if tile.y < 0 or tile.y >= rows.size():
		return true
	var row: String = rows[tile.y]
	if tile.x < 0 or tile.x >= row.length():
		return true
	return bool(DataDB.tiles.get("legend", {}).get(row[tile.x], {}).get("solid", false))


static func tile_center(tile: Vector2i) -> Vector2:
	return Vector2(tile.x * TILE + TILE / 2.0, tile.y * TILE + TILE / 2.0)


static func map_pixel_size(map_data: Dictionary) -> Vector2i:
	var size: Array = map_data.get("size", [0, 0])
	return Vector2i(int(size[0]) * TILE, int(size[1]) * TILE)

extends Node
## 게임 데이터(JSON) 로더. data/ 폴더의 파일을 읽어 사전(Dictionary)으로 보관한다.
## 주의: 내보내기(export) 시 export 필터에 data/*.json 을 포함해야 한다.

var player_def: Dictionary = {}
var skills: Dictionary = {}
var items: Dictionary = {}
var enemies: Dictionary = {}
var dialogue: Dictionary = {}
var quests: Dictionary = {}
var battle_config: Dictionary = {}
var tiles: Dictionary = {}
var growth: Dictionary = {}
var economy: Dictionary = {}
var portraits: Dictionary = {}
var cards: Dictionary = {}
var maps_index: Dictionary = {}
var _map_cache: Dictionary = {}


func _ready() -> void:
	reload()


func reload() -> void:
	player_def = load_json("res://data/characters/player.json")
	skills = load_json("res://data/skills/skills.json")
	items = load_json("res://data/items/items.json")
	enemies = load_json("res://data/enemies/enemies.json")
	dialogue = load_json("res://data/dialogue/cheongpung.json")
	quests = load_json("res://data/quests/quests.json")
	battle_config = load_json("res://data/battle/battle_config.json")
	tiles = load_json("res://data/maps/tiles.json")
	growth = load_json("res://data/characters/growth.json")
	economy = load_json("res://data/items/economy.json")
	portraits = load_json("res://data/characters/portraits.json")
	cards = load_json("res://data/cards/cards.json")
	cards.erase("_comment")
	maps_index = load_json("res://data/maps/maps.json")
	_map_cache.clear()


func get_map(map_id: String) -> Dictionary:
	if _map_cache.has(map_id):
		return _map_cache[map_id]
	var path: String = maps_index.get("maps", {}).get(map_id, "")
	if path == "":
		push_error("알 수 없는 맵: %s" % map_id)
		return {}
	var data := load_json(path)
	_map_cache[map_id] = data
	return data


func has_map(map_id: String) -> bool:
	return maps_index.get("maps", {}).has(map_id)


func item_name(item_id: String) -> String:
	return items.get(item_id, {}).get("name", item_id)


static func load_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		push_error("데이터 파일 없음: %s" % path)
		return {}
	var text := FileAccess.get_file_as_string(path)
	var json := JSON.new()
	var err := json.parse(text)
	if err != OK:
		push_error("JSON 오류 %s (%d행): %s" % [path, json.get_error_line(), json.get_error_message()])
		return {}
	if typeof(json.data) != TYPE_DICTIONARY:
		push_error("JSON 최상위가 객체가 아님: %s" % path)
		return {}
	return json.data


## 화자 이름 + 표정 → 초상화 텍스처 (없으면 null)
func portrait(speaker: String, face: String = "normal") -> Texture2D:
	var pid: String = str(portraits.get(speaker, ""))
	if pid == "":
		return null
	var path := "res://assets/portraits/%s_%s.png" % [pid, face]
	if not ResourceLoader.exists(path):
		path = "res://assets/portraits/%s_normal.png" % pid
	return load(path) if ResourceLoader.exists(path) else null

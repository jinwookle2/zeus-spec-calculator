extends Node2D
## 팻말·항아리·연못 같은 타일 위 조사 지점. 보이지 않지만 상호작용 가능.

var def: Dictionary = {}


func setup(event_def: Dictionary) -> void:
	def = event_def
	name = "Event_" + str(def.get("id", "event"))
	var tile: Array = def.get("tile", [0, 0])
	position = MapBuilder.tile_center(Vector2i(int(tile[0]), int(tile[1])))


func _ready() -> void:
	add_to_group("interactable")


func interact(_player: Node2D) -> void:
	var box := get_tree().get_first_node_in_group("dialogue_box")
	if box:
		await box.run(str(def.get("dialogue", "")))

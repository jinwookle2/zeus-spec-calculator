extends CanvasLayer
## 만복상회: 약초·기력환 구입, 물고기 등 판매.

var _root: Control
var _box: VBoxContainer
var _gold: Label
var _mode := "buy"


func _ready() -> void:
	layer = 45
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build()
	_root.visible = false


func _build() -> void:
	_root = Control.new()
	_root.theme = UiKit.theme()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	var dim := ColorRect.new()
	dim.color = Color(0.04, 0.03, 0.03, 0.5)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(dim)
	var panel := UiKit.panel_container(12)
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	panel.custom_minimum_size = Vector2(360, 230)
	_root.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	panel.add_child(v)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 8)
	v.add_child(head)
	head.add_child(UiKit.brush_label("만복상회", 30, UiKit.TEXT))
	_gold = UiKit.label("", 12, UiKit.NAME)
	_gold.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_gold.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	head.add_child(_gold)
	var tabs := HBoxContainer.new()
	tabs.add_theme_constant_override("separation", 6)
	v.add_child(tabs)
	for t in [["buy", "사기"], ["sell", "팔기"]]:
		var b := UiKit.button(t[1], Vector2(80, 26))
		b.pressed.connect(func(): _mode = t[0]; _refresh())
		tabs.add_child(b)
	var close := UiKit.button("나가기", Vector2(80, 26))
	close.pressed.connect(close_shop)
	tabs.add_child(close)
	_box = VBoxContainer.new()
	_box.add_theme_constant_override("separation", 4)
	v.add_child(_box)


func is_open() -> bool:
	return _root.visible


func open_shop() -> void:
	_root.visible = true
	_mode = "buy"
	GameState.lock_input("shop")
	_refresh()


func close_shop() -> void:
	_root.visible = false
	await get_tree().process_frame
	GameState.unlock_input("shop")


func buy(item_id: String) -> bool:
	var price := int(DataDB.items.get(item_id, {}).get("price", 0))
	if price <= 0 or int(GameState.player["gold"]) < price:
		return false
	GameState.add_gold(-price)
	GameState.add_item(item_id)
	return true


func sell(item_id: String) -> bool:
	var price := int(DataDB.items.get(item_id, {}).get("sell", 0))
	if price <= 0 or not GameState.remove_item(item_id):
		return false
	GameState.add_gold(price)
	return true


func _refresh() -> void:
	for c in _box.get_children():
		c.queue_free()
	_gold.text = "소지금 %d냥" % int(GameState.player["gold"])
	var ids: Array = DataDB.economy.get("shop", {}).get("stock", []) if _mode == "buy" else GameState.inventory.keys()
	var any := false
	for item_id in ids:
		var def: Dictionary = DataDB.items.get(item_id, {})
		var price := int(def.get("price" if _mode == "buy" else "sell", 0))
		if price <= 0:
			continue
		any = true
		var r := HBoxContainer.new()
		r.add_theme_constant_override("separation", 6)
		var icon := TextureRect.new()
		icon.texture = load("res://assets/ui/icons/%s.png" % def.get("icon", "item_herb"))
		r.add_child(icon)
		var l := UiKit.label("%s  %d냥%s" % [def.get("name", item_id), price,
			("  (보유 %d)" % GameState.item_count(item_id))], 12)
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		r.add_child(l)
		var b := UiKit.button("사기" if _mode == "buy" else "팔기", Vector2(56, 24))
		b.disabled = _mode == "buy" and int(GameState.player["gold"]) < price
		b.pressed.connect(func():
			if _mode == "buy":
				buy(item_id)
			else:
				sell(item_id)
			_refresh())
		r.add_child(b)
		_box.add_child(r)
	if not any:
		_box.add_child(UiKit.label("팔 만한 물건이 없다. 연못에서 물고기라도 낚아 오게!" if _mode == "sell" else "", 12, UiKit.DIM))


func _input(event: InputEvent) -> void:
	if _root.visible and (event.is_action_pressed("cancel") or event.is_action_pressed("menu")):
		close_shop()
		get_viewport().set_input_as_handled()

class_name DialogueData
extends RefCounted
## data/dialogue/*.json 의 대사 항목을 현재 게임 상태에 맞게 고른다.


## 조건이 맞는 첫 번째 variant 를 {name, lines:[{speaker,text}], actions} 로 돌려준다.
static func resolve(entry_id: String) -> Dictionary:
	var entry: Dictionary = DataDB.dialogue.get(entry_id, {})
	if entry.is_empty():
		push_warning("대사 없음: %s" % entry_id)
		return {"name": "", "lines": [{"speaker": "", "text": "..."}], "actions": {}}
	var default_name := str(entry.get("name", ""))
	for v in entry.get("variants", []):
		if _conditions_met(v):
			var lines: Array = []
			for line in v.get("lines", []):
				if typeof(line) == TYPE_DICTIONARY:
					lines.append({"speaker": str(line.get("speaker", default_name)), "text": str(line.get("text", "")), "face": str(line.get("face", "normal"))})
				else:
					lines.append({"speaker": default_name, "text": str(line)})
			return {"name": default_name, "lines": lines, "actions": v.get("actions", {})}
	return {"name": default_name, "lines": [], "actions": {}}


static func _conditions_met(v: Dictionary) -> bool:
	for f in _as_array(v.get("if_flag", [])):
		if not GameState.has_flag(f):
			return false
	for f in _as_array(v.get("if_not_flag", [])):
		if GameState.has_flag(f):
			return false
	if v.has("if_quest"):
		var q: Dictionary = v["if_quest"]
		if GameState.get_quest(str(q.get("id", ""))) != str(q.get("state", "")):
			return false
	return true


static func _as_array(v: Variant) -> Array:
	if typeof(v) == TYPE_ARRAY:
		return v
	if typeof(v) == TYPE_STRING and v != "":
		return [v]
	return []


## 대화 종료 후 효과를 적용하고 안내 문구 목록을 돌려준다.
static func apply_actions(actions: Dictionary) -> Array:
	var notices: Array = []
	for f in _as_array(actions.get("set_flags", [])):
		GameState.set_flag(f)
	var gifts: Dictionary = actions.get("give_items", {})
	for item_id in gifts:
		var n := int(gifts[item_id])
		GameState.add_item(item_id, n)
		var nm := DataDB.item_name(item_id)
		notices.append("『%s』 x%d 획득!" % [nm, n])
	if actions.has("quest"):
		var q: Dictionary = actions["quest"]
		var qid := str(q.get("id", ""))
		var before := GameState.get_quest(qid)
		var st := str(q.get("state", ""))
		if before != st:
			GameState.set_quest(qid, st)
			var qname: String = DataDB.quests.get(qid, {}).get("name", qid)
			match st:
				"active":
					notices.append("[임무 시작] %s" % qname)
				"complete":
					notices.append("[임무 완료] %s" % qname)
	if bool(actions.get("heal", false)):
		var p := GameState.player
		if int(p["hp"]) < int(p["max_hp"]) or int(p["mp"]) < int(p["max_mp"]):
			GameState.heal_full()
			notices.append("HP와 MP가 모두 회복되었다!")
	return notices

extends Node
## 로컬 저장/불러오기.
## - 파일: user://savegame.json (+ 직전 저장본 user://savegame.bak)
## - 형식: {"version", "saved_at", "checksum", "data"}
## - 임시 파일에 쓴 뒤 교체하므로 저장 중 강제 종료돼도 기존 저장이 깨지지 않는다.
## - 체크섬/형식이 맞지 않으면 백업본을 시도하고, 그래도 실패하면 안전하게 거부한다.

const SAVE_VERSION := 1

enum LoadResult { OK, NO_SAVE, CORRUPTED, RESTORED_FROM_BACKUP }

var save_dir := "user://"
var save_name := "savegame"
var last_error := ""


func save_path() -> String:
	return save_dir.path_join(save_name + ".json")


func backup_path() -> String:
	return save_dir.path_join(save_name + ".bak")


func temp_path() -> String:
	return save_dir.path_join(save_name + ".tmp")


func has_save() -> bool:
	return FileAccess.file_exists(save_path()) or FileAccess.file_exists(backup_path())


func save_game() -> bool:
	if not GameState.in_game:
		last_error = "진행 중인 게임이 없습니다."
		return false
	var data := GameState.to_dict()
	var envelope := {
		"version": SAVE_VERSION,
		"saved_at": Time.get_datetime_string_from_system(),
		"checksum": _checksum(data),
		"data": data,
	}
	var f := FileAccess.open(temp_path(), FileAccess.WRITE)
	if f == null:
		last_error = "저장 파일을 열 수 없습니다 (%d)." % FileAccess.get_open_error()
		return false
	f.store_string(JSON.stringify(envelope, "\t"))
	f.close()
	var dir := DirAccess.open(save_dir)
	if dir == null:
		last_error = "저장 폴더에 접근할 수 없습니다."
		return false
	if FileAccess.file_exists(save_path()):
		if FileAccess.file_exists(backup_path()):
			dir.remove(backup_path().get_file())
		dir.rename(save_path().get_file(), backup_path().get_file())
	var err := dir.rename(temp_path().get_file(), save_path().get_file())
	if err != OK:
		last_error = "저장 파일 교체 실패 (%d)." % err
		return false
	last_error = ""
	return true


## 저장 데이터를 GameState 에 적용한다.
func load_game() -> LoadResult:
	if not has_save():
		last_error = "저장된 게임이 없습니다."
		return LoadResult.NO_SAVE
	var main := read_envelope(save_path())
	if not main.is_empty() and GameState.apply_dict(main["data"]):
		last_error = ""
		return LoadResult.OK
	var backup := read_envelope(backup_path())
	if not backup.is_empty() and GameState.apply_dict(backup["data"]):
		last_error = "저장 파일이 손상되어 직전 저장본으로 복구했습니다."
		return LoadResult.RESTORED_FROM_BACKUP
	last_error = "저장 파일이 손상되어 불러올 수 없습니다."
	return LoadResult.CORRUPTED


## 파일을 읽고 형식/버전/체크섬을 검사한다. 실패 시 빈 사전.
func read_envelope(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var text := FileAccess.get_file_as_string(path)
	if text.is_empty():
		return {}
	var json := JSON.new()
	if json.parse(text) != OK or typeof(json.data) != TYPE_DICTIONARY:
		return {}
	var env: Dictionary = json.data
	if not env.has("version") or not env.has("data") or typeof(env["data"]) != TYPE_DICTIONARY:
		return {}
	var version := int(env["version"])
	if version > SAVE_VERSION or version < 1:
		return {}
	if str(env.get("checksum", "")) != _checksum(env["data"]):
		return {}
	env["data"] = migrate(env["data"], version)
	return env


## 이전 버전 저장 데이터를 현재 형식으로 변환 (버전이 오르면 여기에 단계 추가).
func migrate(data: Dictionary, from_version: int) -> Dictionary:
	var d := data
	if from_version < 1:
		pass
	return d


func delete_save() -> void:
	var dir := DirAccess.open(save_dir)
	if dir == null:
		return
	for p in [save_path(), backup_path(), temp_path()]:
		if FileAccess.file_exists(p):
			dir.remove(p.get_file())


func save_summary() -> String:
	var env := read_envelope(save_path())
	if env.is_empty():
		env = read_envelope(backup_path())
	if env.is_empty():
		return ""
	var d: Dictionary = env["data"]
	var map_name: String = DataDB.get_map(str(d.get("map", ""))).get("name", "?")
	return "Lv.%d  %s  (%s)" % [int(d["player"]["level"]), map_name, str(env.get("saved_at", "")).replace("T", " ")]


func _checksum(data: Dictionary) -> String:
	# JSON 왕복 후에도 같은 값이 나오도록 정렬된 문자열로 해시
	return JSON.stringify(_normalize(data), "", true).sha256_text()


func _normalize(v: Variant) -> Variant:
	match typeof(v):
		TYPE_DICTIONARY:
			var out := {}
			for k in v:
				out[str(k)] = _normalize(v[k])
			return out
		TYPE_ARRAY:
			var arr := []
			for x in v:
				arr.append(_normalize(x))
			return arr
		TYPE_INT, TYPE_FLOAT:
			# JSON 은 정수/실수를 구분하지 않으므로 숫자를 통일
			var f := float(v)
			if is_equal_approx(f, roundf(f)):
				return "%d" % int(roundf(f))
			return "%.4f" % f
		TYPE_BOOL:
			return v
	return str(v)

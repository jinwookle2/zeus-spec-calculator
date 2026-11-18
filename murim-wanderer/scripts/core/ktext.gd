class_name KText
extends RefCounted
## 한국어 조사 처리 도우미. 예) KText.josa("도윤", "이/가") -> "도윤이"


static func has_batchim(word: String) -> bool:
	if word.is_empty():
		return false
	var code := word.unicode_at(word.length() - 1)
	if code < 0xAC00 or code > 0xD7A3:
		# 한글이 아니면 숫자 끝자리로 대충 판단 (0,1,3,6,7,8 은 받침 있음)
		if code >= 48 and code <= 57:
			return [0, 1, 3, 6, 7, 8].has(code - 48)
		return false
	return (code - 0xAC00) % 28 != 0


static func josa(word: String, pair: String) -> String:
	var parts := pair.split("/")
	if parts.size() != 2:
		return word + pair
	# "으로/로": ㄹ 받침이면 "로"
	if pair == "으로/로" and has_batchim(word):
		var code := word.unicode_at(word.length() - 1)
		if code >= 0xAC00 and (code - 0xAC00) % 28 == 8:
			return word + "로"
	return word + (parts[0] if has_batchim(word) else parts[1])

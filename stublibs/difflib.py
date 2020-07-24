def get_close_matches(word, possibilities, n=3, cutoff=0.6):
	def fold(s):
		return s.lower().replace(" ", "").replace("\t", "")
	for p in possibilities:
		if fold(p) == fold(word):
			return [p]
	return []

from enum import IntEnum
from functools import total_ordering
from itertools import islice, zip_longest
from typing import Iterator, TypeVar

isdigit = lambda s: all(ord("0") <= ord(c) <= ord("9") for c in s)
isalpha = lambda s: all(ord("a") <= ord(c) <= ord("z") for c in s)
isalnum = lambda s: all(isdigit(c) or isalpha(c) for c in s)
a2i = lambda c: ord(c) - ord("a") + 1

T = TypeVar("T")

MODIFIERS = ["alpha", "beta", "pre", "rc", ".", "pl"]

class Modifier(IntEnum):
	Alpha = -3  # 'alpha'
	Beta = -2  # 'beta'
	Pre = -1  # 'pre' or 'rc'
	Dot = 0  # '.', or 'pl'

def parse_mod(raw: str) -> list[Modifier]:
	match raw:
		case "." | "pl":
			return [Modifier.Dot]
		case "alpha":
			return [Modifier.Alpha]
		case "beta":
			return [Modifier.Beta]
		case "pre" | "rc":
			return [Modifier.Pre]

def parse_component(raw: str) -> list[int]:
	if not raw:
		return []
	if isalnum(raw):  # easy cases
		if isdigit(raw):  # all digits
			return [int(raw)]
		if isalpha(raw):  # all alpha
			out = []
			for ch in raw:
				out += [Modifier.Dot, a2i(ch)]
			return out
	acc = ""
	out = []
	raw = iter(raw)
	try:  # hard case (mixed digits/alpha/neither)
		while True:
			ch = next(raw)
			if isalnum(ch):
				if isdigit(ch):
					while isdigit(ch):
						acc += ch
						ch = next(raw)
					out += [int(acc)]
					acc = ""
				if isalpha(ch):
					out += [Modifier.Dot, a2i(ch)]
	except StopIteration:
		if acc:  # clean up
			out += [int(acc)]
		return out

@total_ordering
class Version:
	def __init__(self: T, v: str) -> T:
		self._raw = v
		rest = v.lower()
		ver = []
		while rest:
			for mod in MODIFIERS:
				lhs, mod, rhs = rest.partition(mod)
				if mod:
					ver += parse_component(lhs) + parse_mod(mod)
					rest = rhs
					break
			if not rest:
				break
			elif not any(m in rest for m in MODIFIERS):
				ver += parse_component(rest)
				break
		self._version = tuple(ver)

	def __repr__(self) -> str:
		return f"Version{self._version!r}"

	def __str__(self) -> str:
		return self._raw

	def __hash__(self) -> int:
		return hash(self._raw)

	def __iter__(self) -> Iterator[int | Modifier]:
		return iter(self._version)

	def __len__(self) -> int:
		return len(self._version)

	def __lt__(self: T, other: str | T) -> bool:
		if isinstance(other, str):
			Version(other)
		maxlen = max(len(self), len(other))
		for lhs, rhs in islice(zip_longest(self, other, fillvalue=0), maxlen):
			if lhs < rhs:
				return True
			elif lhs > rhs:
				return False
		return False

	def __eq__(self: T, other: str | T) -> bool:
		if isinstance(other, str):
			Version(other)
		maxlen = max(len(self), len(other))
		for lhs, rhs in islice(zip_longest(self, other, fillvalue=0), maxlen):
			if lhs != rhs:
				return False
		return True


# tests
if __name__ == "__main__":
	assert(Version("1.2") == Version("1.2"))
	assert(Version("A") == Version("a"))
	assert(Version("a") < Version("b"))
	assert(Version("aa") < Version("b"))
	assert(Version("1") == Version("1"))
	assert(Version("1") == Version("1.0"))
	assert(Version("1") == Version("1pl0"))
	assert(Version("1") > Version("0"))
	assert(Version("1") > Version("0.0.1"))
	assert(Version("1") > Version("1pre1"))
	assert(Version("1") > Version("1rc1"))
	assert(Version("1") > Version("1alpha"))
	assert(Version("1") > Version("1alpha1"))
	assert(Version("1") > Version("1beta1"))
	assert(Version("2") > Version("1"))
	assert(Version("1") < Version("2"))
	assert(Version("1") < Version("1.1"))
	assert(Version("1") < Version("1pl1"))
	assert(Version("7.3.2") < Version("7.3ce.1"))
	assert(Version("1ff7acd") == Version("1.6.6+7.1.3.4"))
	assert(Version("1ff77cd") == Version("1.6.6+77.3.4"))

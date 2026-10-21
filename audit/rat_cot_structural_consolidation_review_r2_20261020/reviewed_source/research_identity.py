"""Label-free identities for the supported procedural question templates."""

from functools import lru_cache
import hashlib
import itertools
import json

IDENTITY_VERSION = "procedural-v1"
FAMILIES = ("arith", "order", "g24")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


@lru_cache(maxsize=2048)
def _order_graph(n, clues):
    return min(
        tuple(sorted((clue[0], mapping[clue[1]], mapping[clue[2]], *clue[3:]) for clue in clues))
        for mapping in itertools.permutations(range(n))
    )


def problem_fingerprint(item):
    """Ignore labels, runner names and clue order; retain the asked ordinal."""
    family, metadata = item.get("family"), item.get("meta", {})
    if family not in FAMILIES:
        if family is not None:
            raise ValueError("Unknown procedural family")
        return digest(["curated_group", item["group_id"]])
    if not isinstance(metadata, dict):
        raise ValueError("Procedural metadata must be an object")
    if family == "arith":
        start, steps = metadata.get("start"), metadata.get("steps")
        if not _integer(start) or not isinstance(steps, list) or not steps:
            raise ValueError("Invalid arithmetic metadata")
        for step in steps:
            if not isinstance(step, (list, tuple)) or len(step) != 2 or step[0] not in ("add", "sub", "mul", "div") or not _integer(step[1], 1):
                raise ValueError("Invalid arithmetic operation")
        return digest([family, start, steps])
    if family == "g24":
        numbers = metadata.get("numbers")
        if not isinstance(numbers, list) or len(numbers) != 4 or not all(_integer(n, 1) for n in numbers):
            raise ValueError("Game-of-24 requires four positive integers")
        return digest([family, sorted(numbers)])
    names, clues, ask = metadata.get("names"), metadata.get("clues"), metadata.get("ask")
    if not isinstance(names, list) or not 2 <= len(names) <= 8 or not all(isinstance(name, str) and name.strip() for name in names) or len(set(names)) != len(names):
        raise ValueError("Invalid ordering names")
    n = len(names)
    if not _integer(ask) or ask >= n or not isinstance(clues, list) or not clues:
        raise ValueError("Invalid ordering rank or clues")
    normalized_clues = []
    for clue in clues:
        if not isinstance(clue, (list, tuple)) or len(clue) not in (3, 4) or clue[0] not in ("a", "b", "g", "gap") or not all(_integer(x) and x < n for x in clue[1:3]) or clue[1] == clue[2]:
            raise ValueError("Invalid ordering clue")
        kind, a, b = clue[:3]
        if kind in ("g", "gap"):
            if len(clue) != 4 or not _integer(clue[3], 1) or clue[3] >= n:
                raise ValueError("Invalid ordering gap")
            normalized_clues.append(("g", a, b, clue[3]))
        else:
            if len(clue) == 4 and (type(clue[3]) is not int or clue[3] != (1 if kind == "a" else 0)):
                raise ValueError("Invalid ordering offset")
            # Preserve procedural-v1 identities for legacy three-field clues.
            normalized_clues.append((kind, a, b))
    # Repeated copies of a clue do not change the underlying puzzle.
    canonical = _order_graph(n, tuple(sorted(set(normalized_clues))))
    return digest([family, n, ask, canonical])


def canonical_problem_id(item):
    if item.get("family") not in FAMILIES:
        raise ValueError("Canonical procedural IDs require a known family")
    return f"problem_{item['family']}_{problem_fingerprint(item)}"

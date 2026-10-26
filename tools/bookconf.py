"""Settings of the book, read from book.toml in the book directory (the parent of tools/)."""

import sys
import tomllib
from functools import lru_cache
from pathlib import Path

BOOK = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def conf():
    with open(BOOK / "book.toml", "rb") as f:
        return tomllib.load(f)


def book():
    return conf()["book"]


def source():
    return conf()["source"]


def order():
    """[(kind, file)] in reading order; kind is front, part, ch or app."""
    return [tuple(x) for x in conf()["layout"]["order"]]


def missing():
    """Files in the order that do not exist yet, e.g. chapters not written."""
    return [name for kind, name in order() if not (BOOK / name).exists()]


def written_order():
    """order() without the missing files, each named once on stderr."""
    for name in missing():
        print(f"warning: {name} is in [layout] order but does not exist yet; skipped", file=sys.stderr)
    return [(kind, name) for kind, name in order() if (BOOK / name).exists()]

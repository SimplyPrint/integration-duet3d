"""Include/exclude path filtering for Duet object model queries.

The Duet object model is large and every ``rr_model`` request loads the
firmware (and in SBC mode the DCS<->Duet SPI link, where each request turns
into a ``GetObjectModel`` transfer). The connector only reads a handful of
paths, so fetching is restricted to those subtrees.

Paths are dotted key chains as used by ``M409``/``rr_model`` keys, e.g.
``"move.compensation"``. Array indices are not part of the grammar: lists are
fetched and kept atomically.
"""

from typing import Iterable, Optional, Tuple

import attr

#: Config value meaning "no include filtering, fetch the full object model".
MATCH_ALL = "*"


def _is_under(path: str, base: str) -> bool:
    """Return True if path is base itself or nested below it."""
    return path == base or path.startswith(base + ".")


def _normalize_include(paths: Optional[Iterable[str]]) -> Optional[Tuple[str, ...]]:
    """Deduplicate and drop paths already covered by a broader include."""
    if paths is None:
        return None
    ordered = tuple(dict.fromkeys(paths))
    if MATCH_ALL in ordered:
        return None
    return tuple(
        path for path in ordered
        if not any(path != other and _is_under(path, other) for other in ordered)
    )


@attr.s(frozen=True)
class ObjectModelFilter:
    """Decides which object model paths are fetched and kept.

    ``include=None`` disables include filtering (everything is fetched),
    ``exclude`` always wins over ``include``.
    """

    include = attr.ib(
        type=Optional[Tuple[str, ...]],
        default=None,
        converter=_normalize_include,
    )
    exclude = attr.ib(type=Tuple[str, ...], default=(), converter=tuple)

    def is_excluded(self, path: str) -> bool:
        """Return True if path is at or below an excluded path."""
        return any(_is_under(path, excluded) for excluded in self.exclude)

    def wanted(self, path: str) -> bool:
        """Return True if path lies on the route to, at, or below an included path."""
        if self.is_excluded(path):
            return False
        if self.include is None:
            return True
        return any(
            _is_under(path, included) or _is_under(included, path)
            for included in self.include
        )

    def refetch_paths(self, key: str) -> Tuple[str, ...]:
        """Paths to refetch when the seq counter of a top-level key changes."""
        if self.is_excluded(key):
            return ()
        if self.include is None:
            return (key,)
        return tuple(included for included in self.include if _is_under(included, key))

    def prune(self, tree: dict, path: str = "") -> dict:
        """Return a copy of tree without unwanted branches. Lists are kept atomically."""
        result = {}
        for key, value in tree.items():
            sub_path = f"{path}.{key}" if path else key
            if not self.wanted(sub_path):
                continue
            if isinstance(value, dict):
                value = self.prune(value, sub_path)
            result[key] = value
        return result

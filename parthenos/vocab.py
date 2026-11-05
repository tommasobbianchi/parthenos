"""Living dimension vocabulary.

Dimensions are a *living vocabulary*, not a rigid schema: they can be renamed,
merged, or split at runtime. These operations propagate atomically across the
graph's nodes. Crucially, they never touch floatation dynamics — sink/rise is
behavior-driven, so renaming a dimension must not change a node's trajectory.
"""

from __future__ import annotations

from collections.abc import Callable

from parthenos.graph import GraphStore

Splitter = Callable[[object], tuple[object, object]]


def _default_splitter(value: object) -> tuple[object, object]:
    """Default splitter: the value lands in the first slot, the second is empty."""
    return (value, None)


def _to_set(value: object) -> set:
    """Coerce a dimension value to a set, treating scalars as singletons."""
    if isinstance(value, (set, frozenset)):
        return set(value)
    if isinstance(value, (list, tuple)):
        return set(value)
    return {value}


def _union(x: object, y: object) -> object:
    """Union two dimension values under set semantics.

    Equal values collapse back to the scalar value; otherwise the two singletons
    (or collection elements) are unioned into a set.
    """
    if x == y:
        return x
    return _to_set(x) | _to_set(y)


class DimensionVocabulary:
    """Registry of canonical dimension names + mutation ops that propagate."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store
        self._dims: set[str] = set()

    def register(self, name: str) -> None:
        """Declare a dimension name (idempotent)."""
        self._dims.add(name)

    def rename(self, old: str, new: str) -> None:
        """Rename a dimension across every node. Raises KeyError if `old` is unknown."""
        if old not in self._dims:
            raise KeyError(old)
        self._dims.discard(old)
        self._dims.add(new)
        for node in self._store._nodes.values():
            with node.lock:
                if old not in node.dims:
                    continue
                value = node.dims.pop(old)
                if new in node.dims:
                    node.dims[new] = _union(node.dims[new], value)
                else:
                    node.dims[new] = value

    def merge(self, a: str, b: str, into: str) -> None:
        """Merge two dimensions into one; values collide and are unioned."""
        self._dims.discard(a)
        self._dims.discard(b)
        self._dims.add(into)
        for node in self._store._nodes.values():
            with node.lock:
                has_a = a in node.dims
                has_b = b in node.dims
                va = node.dims.pop(a, None)
                vb = node.dims.pop(b, None)
                if has_a and has_b:
                    node.dims[into] = _union(va, vb)
                elif has_a:
                    node.dims[into] = va
                elif has_b:
                    node.dims[into] = vb

    def split(self, dim: str, a: str, b: str, splitter: Splitter | None = None) -> None:
        """Split one dimension into two using `splitter` (default: value -> (value, None)).

        A ``None`` produced by the splitter leaves that destination dim unset.
        """
        if splitter is None:
            splitter = _default_splitter
        self._dims.discard(dim)
        self._dims.add(a)
        self._dims.add(b)
        for node in self._store._nodes.values():
            with node.lock:
                if dim not in node.dims:
                    continue
                value = node.dims.pop(dim)
                va, vb = splitter(value)
                if va is not None:
                    node.dims[a] = va
                if vb is not None:
                    node.dims[b] = vb

    def names(self) -> frozenset[str]:
        """Snapshot of current dimension names."""
        return frozenset(self._dims)

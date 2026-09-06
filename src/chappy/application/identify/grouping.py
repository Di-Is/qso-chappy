"""Grouping helpers for identify workflows."""

from __future__ import annotations

from collections import defaultdict


class UnionFind:
    """Union-Find data structure for grouping identify temporary lines."""

    __slots__ = ("_parent",)

    def __init__(self, size: int) -> None:
        """Initialize disjoint sets.

        Args:
            size: Number of initial singleton sets.
        """
        self._parent = {index: index for index in range(size)}

    def find(self, index: int) -> int:
        """Find the root for an index with path compression.

        Args:
            index: Index to resolve.

        Returns:
            Root index.
        """
        if self._parent[index] != index:
            self._parent[index] = self.find(self._parent[index])
        return self._parent[index]

    def union(self, left: int, right: int) -> None:
        """Union two sets.

        Args:
            left: Left index.
            right: Right index.
        """
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self._parent[left_root] = right_root

    def collect_groups(self) -> dict[int, list[int]]:
        """Collect indices grouped by their root.

        Returns:
            Mapping of root index to member indices.
        """
        groups: dict[int, list[int]] = defaultdict(list)
        for index in self._parent:
            groups[self.find(index)].append(index)
        return groups

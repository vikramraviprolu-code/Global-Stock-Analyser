"""SymbolResolver — wraps the existing resolver.search() function."""
from __future__ import annotations
from typing import List, Protocol

from resolver import search as _search, needs_disambiguation as _needs_disambig


class SymbolResolver(Protocol):
    def resolve(self, query: str, limit: int = 10) -> List[dict]: ...
    def needs_choice(self, candidates: List[dict], query: str) -> bool: ...


class DefaultSymbolResolver:
    def resolve(self, query: str, limit: int = 10) -> List[dict]:
        return _search(query, limit=limit)

    def needs_choice(self, candidates: List[dict], query: str) -> bool:
        return _needs_disambig(candidates, query)

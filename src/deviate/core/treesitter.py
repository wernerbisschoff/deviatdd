from __future__ import annotations


def extract_changed_symbols(diff_text: str) -> list[dict]:
    raise NotImplementedError


def extract_file_structure(source: str) -> dict:
    raise NotImplementedError


def incremental_parse(source: str, old_tree=None):
    raise NotImplementedError

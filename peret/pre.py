""" preprocessing functions for properties extracted from BTS json and AED
html sources.
"""
from functools import reduce

from .providers import register_qualified_property

INVERSE = dict(
    reduce(
        lambda l, e: l + [e, e[::-1]],
        [
            ("partOf", "contains"),
            ("predecessor", "successor"),
            ("rootOf", "root"),
            ("referencedBy", "referencing"),
        ],
        []
    )
)


def _verify_relations(_: str, entry: dict, wlist: dict) -> dict:
    """ Remove relations of which the targets don't exist.

    >>> wlist = {'2': {}}
    >>> _verify_relations('1',
    ... {'relations': {'partOf': ['2', '3'], 'root': ['4']}}, wlist)
    {'relations': {'partOf': ['2'], 'root': []}}

    """
    entry['relations'] = {
        predicate: list(filter(
            lambda value: value in wlist,
            values
        ))
        for predicate, values in entry.get('relations', {}).items()
    }
    return entry


def _mirror_relations(entry_id: str, entry: dict, wlist: dict) -> dict:
    """ create inverted relations in wlist entries referenced
    via an entry's relations.

    >>> wlist = {'2': {}}
    >>> e = _mirror_relations('1', {'relations': {'root': ['2']}}, wlist)
    >>> wlist
    {'2': {'relations': {'rootOf': ['1']}}}

    """
    for predicate, values in entry.get('relations', {}).items():
        for value in values:
            if value == entry_id:
                print(f'{value=} same as {entry_id=}! ({predicate=})')
                continue
            target = wlist.get(value, {})
            target['relations'] = register_qualified_property(
                target.get('relations', {}), INVERSE[predicate], entry_id
            )
    return entry

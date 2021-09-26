""" functions for processing data from 2018 BTS couchdb dump.
"""
from typing import Iterable, List, Callable

import json
from zipfile import ZipFile
from functools import reduce

from . import register_qualified_property


def load_wlist(filename: str = 'dump/vocabulary.zip') -> Iterable[dict]:
    """ load lemma list from BTS couchdb dump ZIP file.
    Returns a generator.

    >>> len(list(load_wlist()))
    38775

    """
    with ZipFile(filename) as z:
        with z.open('aaew_wlist.json') as f:
            wlist = json.load(f)
    yield from wlist


def get_translations(bts_entry: dict) -> dict:
    """ extract translations from BTS couchdb dump JSON object and group
    them under their language values.

    >>> t = {'value': 'vulture', 'lang': 'en'}
    >>> get_translations({'translations': {'translations': [t]}})
    {'translations': {'en': ['vulture']}}

    """
    res = {}
    for translation in bts_entry.get('translations', {}).get(
        'translations', []
    ):
        register_qualified_property(
            res, translation.get('lang'), translation.get('value')
        )
    return {'translations': res}


def get_relations(bts_entry: dict) -> dict:
    """ extract relations of BTS couchdb dump JSON object and group them
    under their respective predicates.

    >>> r = {'type': 'rootOf', 'objectId': '48620'}
    >>> get_relations({'relations': [r]})
    {'relations': {'rootOf': ['48620']}}

    """
    res = {}
    for relation in bts_entry.get('relations', []):
        register_qualified_property(
            res, relation.get('type'), relation.get('objectId')
        )
    return {'relations': res}


def apply_functions(
    entry: dict, functions: List[Callable] = [get_translations]
) -> dict:
    """ apply a list of functions to a BTS couchdb dump entry in order to
    extract and transform properties.

    >>> f1 = lambda e: {'a': e['A']}
    >>> f2 = lambda e: {'b': e['B']}
    >>> apply_functions({'A': 1, 'B': 2}, functions=[f1, f2])
    {'a': 1, 'b': 2}

    """
    return reduce(
        lambda a, b: {**a, **b},
        [f(entry) for f in functions],
        {}
    )


def init_wlist(
    filename: str = 'dump/vocabulary.zip',
    functions: List[Callable] = [get_translations],
) -> dict:
    """ load lemma list from BTS couchdb dump ZIP file and create a dict which
    assigns extracted properties of each lemma entry to its `_id`.
    Custom functions can be passed to be used to extract properties from the
    BTS lemma entries.

    >>> f = lambda entry: {'id': entry['_id']}
    >>> init_wlist(functions=[f])['1']
    {'id': '1'}

    >>> init_wlist()['1']['translations']
    {'de': ['Geier; Vogel (allg.)'], 'en': ['vulture; bird (gen.)']}

    """
    return {
        entry['_id']: apply_functions(entry, functions)
        for entry in load_wlist(filename=filename)
    }

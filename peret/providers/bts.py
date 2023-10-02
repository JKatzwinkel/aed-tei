""" functions for processing data from 2018 BTS couchdb dump.
"""
from typing import Iterable, List, Callable

import json
from zipfile import ZipFile
from functools import reduce

from . import register_qualified_property


def load_vocabulary(
    filename: str = 'dump/vocabulary.zip',
    vocab: str = 'aaew_wlist',
) -> Iterable[dict]:
    """
    load lemma list from BTS couchdb dump ZIP file.
    Returns a generator.

    >>> fn = 'test/dump/vocabulary.zip'
    >>> len(list(load_vocabulary(filename=fn)))
    2

    >>> len(list(load_vocabulary(filename=fn, vocab='aaew_ths')))
    5

    """
    with ZipFile(filename) as z:
        with z.open(f'{vocab}.json') as f:
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


def extract_passport_values(node: dict, path: str) -> list:
    """ recursively traverse passport tree in attempt to extract value(s)
    addressed by dot-seperated path.

    >>> c1={'type': 'c', 'value': 2}
    >>> extract_passport_values(c1, 'c')
    [2]

    >>> extract_passport_values({'children': [c1]}, '.c')
    [2]

    >>> c2={'type': 'c', 'value': 3}
    >>> b={'children': [c1, c2], 'type': 'b'}
    >>> a={'children': [b], 'type': 'a'}
    >>> p={'children': [a]}
    >>> extract_passport_values(p, '.a.b.c')
    [2, 3]

    >>> b['children'].append({'type': 'd'})
    >>> extract_passport_values(p, '.a.b.d')
    []

    """
    res = []
    segments = path.split('.')
    if len(segments) == 1 and node.get('type') == segments[-1]:
        return [val] if (val := node.get('value')) else []
    for child in node.get(segments[0], node).get('children', []):
        res += extract_passport_values(
            child, '.'.join(segments[1:])
        )
    return res


def get_ths_entry_dates(bts_entry: dict) -> dict:
    """ extract BTS date thesaurus entry boundaries from passport.

    >>> d1 = {'type': 'beginning', 'value': '-250'}
    >>> d2 = {'type': 'end', 'value': '-201'}
    >>> mg = {'type': 'main_group', 'children': [d1, d2]}
    >>> td = {'type': 'thesaurus_date', 'children': [mg]}
    >>> entry = {'passport': {'children': [td]}, 'type': 'date'}
    >>> get_ths_entry_dates(entry)
    {'dates': {'beginning': ['-250'], 'end': ['-201']}}

    """
    return {
        'dates': {
            key: extract_passport_values(
                bts_entry.get('passport', {}),
                f'.thesaurus_date.main_group.{key}'
            )
            for key in ['beginning', 'end']
            if bts_entry.get('type') == 'date'
        }
    }


def fill_in_missing_dateranges(entry_id: str, entry: dict, ths: dict) -> dict:
    '''

    >>> fill_in_missing_dateranges(
    ...     'FMNBFXWGA5C2TEXFRDXOGXBEPE',
    ...     {'dates': {'beginning': ['-250'], 'end': ['-201']}}, {})
    {'dates': {'beginning': ['-5000'], 'end': ['-3900']}}

    '''
    missing_dateranges = {
        'MXWX4WG43ZHI7D4RLTGK3IBGXY': ['-5500', '  900'],  # 9 = Datierungen
        'FKLXKTC5RJFSZCBDU5HWK6KHGU': ['-5500', '  900'],  # (unbekannt)
        'GTIHALKZWJFTNCLZ3ITXK7HBXA': ['-5500', '  900'],  # (unbestimmt)
        'DUVGWT7GSRCKDM5LFTGU6MZ3GY': ['-5500', '  641'],  # (Epochen und Dynastien)
        '6YAAR2WRI5F6BLP6YMW3G67P6Q': ['-5500', '-5000'],  # Neolithikum vor der Badari-Kultur
        'FMNBFXWGA5C2TEXFRDXOGXBEPE': ['-5000', '-3900'],  # Badari-Kultur
        'P5F2WOP6YZGBHK5KCSCP2UXJHM': ['-3900', '-3650'],  # Naqada I
        'WLIRCHQ3DRF4ZOTIREDVCPKC5A': ['-3650', '-3300'],  # Naqada II
        'IPXSCTKV4REDHIXWTZWDXVXJWY': ['-3300', '-3151'],  # Naqada III
        'MM4QYACJOJCCLJWBD6VAX2FLKE': ['-2135', '-1794'],  # Mittleres Reich
        'JS32JKX2CNG25GZ3B6MGYMDU4I': ['-1070', ' -656'],  # Dritte Zwischenzeit
        'HYYNMJRFTVFIHB7JUA6M2QW3LQ': [' -332', '  -30'],  # Makedonen, Ptolemäer
        'D3R5CH5NZBDA7IZMCKKJPWYZKU': [' -900', '   -1'],  # (Jahrhunderte v.Chr.)
        'FHZEINDCEJAOTHIVC35NYGMC2Q': ['    1', '  900'],  # (Jahrhunderte n.Chr.)
    }
    if amendment := missing_dateranges.get(entry_id):
        entry['dates'] |= {'beginning': [amendment[0]], 'end': [amendment[1]]}
    return entry


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


def init_vocab(
    filename: str = 'dump/vocabulary.zip',
    vocab: str = 'aaew_wlist',
    functions: List[Callable] = [get_translations],
) -> dict:
    """ load lemma list from BTS couchdb dump ZIP file and create a dict which
    assigns extracted properties of each lemma entry to its `_id`.
    Custom functions can be passed to be used to extract properties from the
    BTS lemma entries.

    >>> f = lambda entry: {'id': entry['_id']}
    >>> fn = 'test/dump/vocabulary.zip'
    >>> init_vocab(filename=fn, functions=[f])['1']
    {'id': '1'}

    >>> init_vocab(filename=fn)['1']['translations']
    {'de': ['Geier; Vogel (allg.)'], 'en': ['vulture; bird (gen.)']}

    """
    return {
        entry['_id']: apply_functions(entry, functions)
        for entry in load_vocabulary(
            filename=filename,
            vocab=vocab,
        )
    }

"""
Usage:
    peret.py format [ -f FILE ]
    peret.py add-translations [ -i FILE ]
    peret.py validate [ -f FILE ]

Commands:
    format                  prettify XML file
    add-translations        add translations from BTS couchdb dump zip file to
                            AED-TEI XML dictionary file
    validate                validate an AED TEI file against the XML schema in
                            files/aed_schema.xsd

Options:
    -f FILE --file FILE     path to local XML file
                            [default: files/dictionary.xml]
    -i FILE --input FILE    path to BTS couchdb dump zip file
                            [default: dump/vocabulary.zip]

"""
from typing import Iterable, List, Callable

import json
from pathlib import Path
from zipfile import ZipFile
from functools import reduce

import docopt
from delb import Document, TagNode, new_tag_node  # pylint: disable=import-error # noqa: E501
import xmlschema  # pylint: disable=import-error

XML_NS = "http://www.w3.org/XML/1998/namespace"
RELATIONS = dict(
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


def _load_wlist(filename: str = 'dump/vocabulary.zip') -> Iterable[dict]:
    """ load lemma list from BTS couchdb dump ZIP file.
    Returns a generator.

    >>> len(list(_load_wlist()))
    38775

    """
    with ZipFile(filename) as z:
        with z.open('aaew_wlist.json') as f:
            wlist = json.load(f)
    yield from wlist


def _register_bts_qualified_property(
    registry: dict, qualifier: str, value: str
) -> dict:
    """ add a value to the list stored under the accompaning qualifier.

    >>> _register_bts_qualified_property({}, 'k', 'v')
    {'k': ['v']}

    """
    if qualifier and value:
        registry[qualifier] = registry.get(qualifier, []) + [value]
    return registry


def _translations(bts_entry: dict) -> dict:
    """ extract translations from BTS couchdb dump JSON object and group
    them under their language values.

    >>> t = {'value': 'vulture', 'lang': 'en'}
    >>> _translations({'translations': {'translations': [t]}})
    {'translations': {'en': ['vulture']}}

    """
    res = {}
    for translation in bts_entry.get('translations', {}).get(
        'translations', []
    ):
        _register_bts_qualified_property(
            res, translation.get('lang'), translation.get('value')
        )
    return {'translations': res}


def _relations(bts_entry: dict) -> dict:
    """ extract relations of BTS couchdb dump JSON object and group them
    under their respective predicates.

    >>> r = {'type': 'rootOf', 'objectId': '48620'}
    >>> _relations({'relations': [r]})
    {'relations': {'rootOf': ['48620']}}

    """
    res = {}
    for relation in bts_entry.get('relations', []):
        _register_bts_qualified_property(
            res, relation.get('type'), relation.get('objectId')
        )
    return {'relations': res}


def _has_translation(e: TagNode, lang: str, value: str) -> bool:
    """ determine if `<entry/>`-XML element already contains certain
    translation.

    >>> e = Document(
    ... '''<entry><sense><cit type="translation" xml:lang="en">
    ... <quote>vulture</quote></cit></sense></entry>'''
    ... )
    >>> _has_translation(e, 'en', 'vulture')
    True
    >>> _has_translation(e, 'de', 'geier')
    False
    >>> _has_translation(e, 'de', '')
    True

    """
    if value.strip() == '':
        return True
    e.namespaces['xml'] = XML_NS
    for quote in e.css_select(
        f'sense > cit[type="translation"][xml|lang="{lang}"] > quote'
    ):
        if value in map(str, quote.child_nodes()):
            return True
    return False


def _add_translation(e: TagNode, lang: str, value: str) -> TagNode:
    """ add translation to `<entry/>` node.

    >>> e = Document('<entry/>').root
    >>> str(_add_translation(e, 'de', 'geier'))
    '<entry><sense><cit type="translation" xml:lang="de"><quote>geier</quote>\
</cit></sense></entry>'

    """
    if len(e.css_select('sense')) < 1:
        e.append_child(new_tag_node('sense'))
    sense = e.css_select('sense')[0]
    cit = new_tag_node(
        'cit',
        attributes={
            'type': 'translation',
            f'{{{XML_NS}}}lang': lang,
        },
        children=[
            new_tag_node(
                'quote',
                children=[value]
            )
        ]
    )
    sense.append_child(cit)
    return e


def _mirror_relations(entry_id: str, entry: dict, wlist: dict):
    """ create inverted relations in wlist entries referenced
    via an entry's relations.

    >>> wlist = {'2': {}}
    >>> _mirror_relations('1', {'relations': {'root': ['2']}}, wlist)
    >>> wlist
    {'2': {'relations': {'rootOf': ['1']}}}
    """
    for predicate, values in entry.get('relations', {}).items():
        for value in values:
            target = wlist.get(value, {})
            target['relations'] = _register_bts_qualified_property(
                target.get('relations', {}), RELATIONS[predicate], entry_id
            )


def _apply_functions(
    entry: dict, functions: List[Callable] = [_translations]
) -> dict:
    """ apply a list of functions to a BTS couchdb dump entry in order to
    extract and transform properties.

    >>> f1 = lambda e: {'a': e['A']}
    >>> f2 = lambda e: {'b': e['B']}
    >>> _apply_functions({'A': 1, 'B': 2}, functions=[f1, f2])
    {'a': 1, 'b': 2}

    """
    return reduce(
        lambda a, b: {**a, **b},
        [f(entry) for f in functions],
        {}
    )


def init_wlist(
    filename: str = 'dump/vocabulary.zip',
    functions: List[Callable] = [_translations],
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
        entry['_id']: _apply_functions(entry, functions)
        for entry in _load_wlist(filename=filename)
    }


def patch_wlist(wlist: dict, functions: List[Callable] = None) -> dict:
    """ iterate through all key value pairs in wlist and apply one or more
    functions to each.

    >>> wlist = {'1': {}, '2': {'relations': {'rootOf': ['1']}}}
    >>> patch_wlist(wlist, [_mirror_relations])['1']
    {'relations': {'root': ['2']}}

    """
    for _id, entry in wlist.items():
        for func in functions:
            func(_id, entry, wlist)
    return wlist


def _strip_id(aedid: str) -> str:
    """ remove `tla`-prefix from string

    >>> _strip_id('tla113')
    '113'
    >>> _strip_id('113')
    '113'

    """
    return aedid.split('tla', maxsplit=1)[-1]


def _get_id(entry: TagNode) -> str:
    """ get value of a node's `xml:id` attribute

    >>> e = new_tag_node('entry', attributes={f'{{{XML_NS}}}id': '1'})
    >>> _get_id(e)
    '1'

    """
    # pylint: disable=protected-access
    return _strip_id(
        entry._etree_obj.xpath('@xml:id')[0]
    )


def add_lemma_translations(
    inputfile: str = 'dump/vocabulary.zip',
    xmlfile: str = 'files/dictionary.xml'
):
    """ extract translations from BTS couchdb dump ZIP file and insert them
    into AED-TEI XML file.
    """
    print(f'add translations from {inputfile} to {xmlfile}')
    wlist = init_wlist(
        filename=inputfile,
        functions=[_translations]
    )
    aed = Document(Path(xmlfile))
    added = {'entries': set(), 'translations': 0}
    for entry in aed.css_select('entry'):
        _id = _get_id(entry)
        for lang, values in wlist.get(_id, {}).get('translations', {}).items():
            for value in values:
                if not _has_translation(entry, lang, value):
                    _add_translation(entry, lang, value)
                    added['translations'] += 1
                    added['entries'].add(_id)
    print(
        (
            f'added {added["translations"]} translations to '
            f'{len(added["entries"])} entries.'
        )
    )
    aed.save(Path(xmlfile), pretty=True)


def prettify_file(filename: str):
    """ format XML file.
    """
    fp = Path(filename)
    if not fp.exists():
        print(f'XML file {filename} could not be found.')
        return
    Document(fp).save(fp, pretty=True)


def validate_file(filename: str):
    """ validate XML file against AED XSD.
    """
    print(f'validate file {filename}...')
    xsd = xmlschema.XMLSchema11('files/aed_schema.xsd')
    xsd.validate(filename)


def main(**args):
    """ execute cli commands
    """
    if args['format']:
        print(f'prettify XML file {args["--file"]}')
        prettify_file(args['--file'])
    if args['add-translations']:
        add_lemma_translations(args['--input'], args['--file'])
    if args['validate']:
        validate_file(args['--file'])


if __name__ == '__main__':
    main(
        **docopt.docopt(__doc__)
    )

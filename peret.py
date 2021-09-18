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

from pathlib import Path
import json
from zipfile import ZipFile
from functools import reduce

import docopt
from delb import Document, TagNode, new_tag_node  # pylint: disable=import-error # noqa: E501
import xmlschema  # pylint: disable=import-error

XML_NS = "http://www.w3.org/XML/1998/namespace"


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


def _translations(lemma_entry: dict) -> dict:
    """
    >>> t = {'value': 'vulture', 'lang': 'en'}
    >>> _translations({'translations': {'translations': [t]}})
    {'translations': {'en': ['vulture']}}
    """
    res = {}
    for translation in lemma_entry.get('translations', {}).get(
        'translations', []
    ):
        lang = translation.get('lang')
        val = translation.get('value')
        if lang is not None and val is not None:
            res[lang] = res.get(lang, []) + [val]
    return {'translations': res}


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
        e.append_child(e.new_tag_node('sense'))
    sense = e.css_select('sense')[0]
    cit = e.new_tag_node(
        'cit',
        attributes={
            'type': 'translation',
            f'{{{XML_NS}}}lang': lang,
        },
        children=[
            e.new_tag_node(
                'quote',
                children=[value]
            )
        ]
    )
    sense.append_child(cit)
    return e


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


def _strip_id(aedid: str) -> str:
    """ remove `tla`-prefix from string
    >>> _strip_id('tla113')
    '113'
    >>> _strip_id('113')
    '113'
    """
    return aedid.split('tla', maxsplit=1)[-1]


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
        _id = _strip_id(entry._etree_obj.xpath('@xml:id')[0])
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

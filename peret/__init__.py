"""
Usage:
    peret.py format [ -f FILE ]
    peret.py validate [ -f FILE ]
    peret.py add-translations [ -i FILE ] [ -f FILE ]
    peret.py add-relations [ -i FILE ] [ -f FILE ]

Commands:
    format                  prettify XML file
    validate                validate an AED TEI file against the XML schema in
                            files/aed_schema.xsd

    add-translations        add translations from BTS couchdb dump zip file to
                            AED-TEI XML dictionary file
    add-relations           add relations from BTS couchdb dump zip file to
                            AED-TEI XML dictionary file

Options:
    -f FILE --file FILE     path to local XML file
                            [default: files/dictionary.xml]
    -i FILE --input FILE    path to BTS couchdb dump zip file
                            [default: dump/vocabulary.zip]

"""
from typing import List, Callable

from pathlib import Path
from functools import reduce

import docopt
from delb import Document, TagNode  # pylint: disable=import-error
import xmlschema  # pylint: disable=import-error

from .providers import (
    bts,
    register_qualified_property,
)

XML_NS = "http://www.w3.org/XML/1998/namespace"
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


def _has_relation(e: TagNode, predicate: str, value: str) -> bool:
    """ determine whether `<entry/>` element contains specified relation.

    >>> e = Document(
    ... '<entry><xr type="root"><ref target="tla1"/></xr></entry>'
    ... )
    >>> _has_relation(e, 'root', '1')
    True

    """
    if value.strip() == '':
        return True
    return len(
        e.css_select(
            f'entry > xr[type="{predicate}"] > ref[target="tla{value}"]'
        )
    ) > 0


def _add_relation(e: TagNode, predicate: str, value: str) -> TagNode:
    """ add relation to `<entry/>` node.

    >>> e = Document('<entry/>').root
    >>> e =_add_relation(e, 'rootOf', '1')
    >>> e =_add_relation(e, 'partOf', '3')
    >>> str(_add_relation(e, 'partOf', '2'))
    '<entry><xr type="rootOf"><ref target="tla1"/></xr>\
<xr type="partOf"><ref target="tla3"/><ref target="tla2"/></xr></entry>'

    """
    if len(e.xpath(f'./xr[@type="{predicate}"]')) < 1:
        e.append_child(
            e.new_tag_node(
                'xr', attributes={'type': predicate}
            )
        )
    e.xpath(f'./xr[@type="{predicate}"]')[0].append_child(
        e.new_tag_node(
            'ref', attributes={'target': f'tla{value}'},
        )
    )
    return e


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
        f'entry > sense > cit[type="translation"][xml|lang="{lang}"] > quote'
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
    if len(e.css_select('entry > sense')) < 1:
        e.append_child(
            e.new_tag_node('sense')
        )
    e.css_select('entry > sense')[0].append_child(
        e.new_tag_node(
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
    )
    return e


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


def patch_wlist(wlist: dict, functions: List[Callable] = None) -> dict:
    """ iterate through all key value pairs in wlist and apply one or more
    functions to each.

    >>> wlist = {'1': {'relations': {'root': ['3']}},
    ... '2': {'relations': {'rootOf': ['1']}}}
    >>> patch_wlist(wlist, [_verify_relations, _mirror_relations])['1']
    {'relations': {'root': ['2']}}

    """
    for _id, entry in wlist.items():
        for func in functions:
            wlist[_id] = func(_id, entry, wlist)
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

    >>> from delb import new_tag_node
    >>> e = new_tag_node('entry', attributes={f'{{{XML_NS}}}id': '1'})
    >>> _get_id(e)
    '1'

    """
    # pylint: disable=protected-access
    return _strip_id(
        entry._etree_obj.xpath('@xml:id')[0]
    )


def process_wlist(
    inputfile: str = 'dump/vocabulary.zip',
    xmlfile: str = 'files/dictionary.xml',
    extract_funcs: List[Callable] = None,
    prep_funcs: List[Callable] = None,
    prop: str = None,
    _has: Callable = None,
    _add: Callable = None,
):
    """ process entries of AED TEI XML file according to configuration
    and save result to the same XML file.
    """
    print(f'add {prop} from {inputfile} to {xmlfile}')
    print(f'load xml file {xmlfile}')
    aed = Document(Path(xmlfile))
    xml_ids = set(
        map(
            _get_id,
            aed.css_select('entry')
        )
    )
    print('initialize registry')
    wlist = {
        _id: entry
        for _id, entry in patch_wlist(
            {
                _id: entry
                for _id, entry in bts.init_wlist(
                    filename=inputfile,
                    functions=extract_funcs
                ).items()
                if _id in xml_ids
            },
            functions=prep_funcs or []
        ).items()
        if _id in xml_ids
    }
    print('process XML entries')
    _stats = {'entries': set(), 'elements': 0}
    for entry in aed.css_select('entry'):
        _id = _get_id(entry)
        for _type, values in wlist.get(_id, {}).get(prop, {}).items():
            for value in values:
                if not _has(entry, _type, value):
                    _add(entry, _type, value)
                    _stats['elements'] += 1
                    _stats['entries'].add(_id)
    print(
        (
            f'added {_stats["elements"]} {prop} to '
            f'{len(_stats["entries"])} entries.'
        )
    )
    print(f'save results to {xmlfile}')
    aed.save(Path(xmlfile), pretty=True)


def add_lemma_relations(
    inputfile: str = 'dump/vocabulary.zip',
    xmlfile: str = 'files/dictionary.xml'
):
    """ extract relations from BTS couchdb dump ZIP file and insert them
    into AED-TEI XML file.
    """
    process_wlist(
        inputfile=inputfile, xmlfile=xmlfile,
        extract_funcs=[bts.get_relations],
        prep_funcs=[_verify_relations, _mirror_relations],
        prop='relations', _has=_has_relation, _add=_add_relation
    )


def add_lemma_translations(
    inputfile: str = 'dump/vocabulary.zip',
    xmlfile: str = 'files/dictionary.xml'
):
    """ extract translations from BTS couchdb dump ZIP file and insert them
    into AED-TEI XML file.
    """
    process_wlist(
        inputfile=inputfile, xmlfile=xmlfile,
        extract_funcs=[bts.get_translations], prop='translations',
        _has=_has_translation, _add=_add_translation
    )


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


def main():
    """ execute cli commands
    """
    args = docopt.docopt(__doc__)
    if args['format']:
        print(f'prettify XML file {args["--file"]}')
        prettify_file(args['--file'])
    if args['add-translations']:
        add_lemma_translations(args['--input'], args['--file'])
    if args['add-relations']:
        add_lemma_relations(args['--input'], args['--file'])
    if args['validate']:
        validate_file(args['--file'])


if __name__ == '__main__':
    main()

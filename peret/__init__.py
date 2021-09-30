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
from delb import Document, TagNode, tag  # pylint: disable=import-error
import xmlschema  # pylint: disable=import-error

from .proc import (
    XML_NS,
    SourceDef,
    TargetDef,
    PropertyAddition,
    PropertyExtraction,
    _get_id,
)

from .providers import (
    bts,
    register_qualified_property,
)

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
DATERANGE_BOUNDS = {
    'beginning': 'from',
    'end': 'to'
}


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
    return e.css_select(
        f'entry > xr[type="{predicate}"] > ref[target="tla{value}"]'
    ).size > 0


def _add_relation(e: TagNode, predicate: str, value: str) -> TagNode:
    """ add relation to `<entry/>` node.

    >>> e = Document('<entry/>').root
    >>> e = _add_relation(e, 'rootOf', '1')
    >>> e = _add_relation(e, 'partOf', '3')
    >>> str(_add_relation(e, 'partOf', '2'))
    '<entry><xr type="rootOf"><ref target="tla1"/></xr>\
<xr type="partOf"><ref target="tla3"/><ref target="tla2"/></xr></entry>'

    """
    if not e.xpath(f'./xr[@type="{predicate}"]'):
        e.append_child(tag("xr", {"type": predicate}))
    e.xpath(f'./xr[@type="{predicate}"]').first.append_child(
        tag(
            "ref",
            {"target": f"tla{value}"},
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
    return e.css_select(
        f'entry > sense > cit[type="translation"][xml|lang="{lang}"] > quote'
    ).filtered_by(
        lambda quote: quote.full_text == value
    ).size > 0


def _add_translation(e: TagNode, lang: str, value: str) -> TagNode:
    """ add translation to `<entry/>` node.

    >>> e = Document('<entry/>').root
    >>> str(_add_translation(e, 'de', 'geier'))
    '<entry><sense><cit type="translation" xml:lang="de"><quote>geier</quote>\
</cit></sense></entry>'

    """
    if not e.css_select("entry > sense"):
        e.append_child(tag("sense"))
    e.css_select("entry > sense").first.append_child(
        tag(
            "cit",
            {"type": "translation", f"{{{XML_NS}}}lang": lang},
            tag("quote", value),
        )
    )
    return e


def _has_daterange(e: TagNode, pred: str, value: str) -> bool:
    """

    >>> e = Document(
    ... '''<category><catDesc><date from="-1745" to="-1730"/>
    ... Sebekhotep IV.</catDesc></category>'''
    ... )
    >>> _has_daterange(e, 'beginning', '-1745')
    True

    >>> _has_daterange(e, 'end', '-1731')
    False

    """
    attribute = DATERANGE_BOUNDS.get(pred)
    return e.css_select(
        f'category > catDesc > date[{attribute}="{value}"]'
    ).size > 0


def _add_daterange(e: TagNode, pred: str, value: str) -> TagNode:
    """ add daterange to `<category>` node in AED thesaurus.

    >>> e = Document('<category/>').root
    >>> e = _add_daterange(e, 'beginning', '-1745')
    >>> str(_add_daterange(e, 'end', '-1730'))
    '<category><catDesc><date from="-1745" to="-1730"/></catDesc></category>'

    """
    if not e.css_select("category > catDesc"):
        e.append_child(tag("catDesc"))
    if not e.css_select("category > catDesc > date"):
        e.css_select("category > catDesc").first.append_child(tag("date"))
    e.css_select("category > catDesc > date").first.attributes[
        DATERANGE_BOUNDS.get(pred)
    ] = value
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


def patch_vocab(vocab: dict, functions: List[Callable] = None) -> dict:
    """ iterate through all key value pairs in vocab registry and apply one or more
    functions to each.

    >>> wlist = {'1': {'relations': {'root': ['3']}},
    ... '2': {'relations': {'rootOf': ['1']}}}
    >>> patch_vocab(wlist, [_verify_relations, _mirror_relations])['1']
    {'relations': {'root': ['2']}}

    """
    for _id, entry in vocab.items():
        for func in functions:
            vocab[_id] = func(_id, entry, vocab)
    return vocab


def process_vocab(
    src: SourceDef,
    target: TargetDef,
    extraction: PropertyExtraction,
    amendment: PropertyAddition = None,
):
    """ process entries of AED TEI XML file according to configuration
    and save result to the same XML file.
    """
    print(
        f'add {amendment.property_name} from {src.archive} to {target.xmlfile}'
    )
    xml_ids = target.get_ids()
    print('initialize registry')
    wlist = {
        _id: entry
        for _id, entry in patch_vocab(
            {
                _id: entry
                for _id, entry in bts.init_vocab(
                    filename=src.archive,
                    vocab=src.vocab,
                    functions=extraction.extract_funcs or []
                ).items()
                if _id in xml_ids
            },
            functions=extraction.patch_funcs or []
        ).items()
        if _id in xml_ids
    }
    print('process XML entries')
    _stats = {'entries': set(), 'elements': 0}
    for entry in target.get_elements():
        _id = _get_id(entry)
        for _type, values in wlist.get(_id, {}).get(
            amendment.property_name, {}
        ).items():
            for value in values:
                if not amendment.has_property(entry, _type, value):
                    amendment.add_property(entry, _type, value)
                    _stats['elements'] += 1
                    _stats['entries'].add(_id)
    print(
        (
            f'added {_stats["elements"]} {amendment.property_name} to '
            f'{len(_stats["entries"])} entries.'
        )
    )
    target.save()


def add_lemma_relations(
    inputfile: str = 'dump/vocabulary.zip',
    xmlfile: str = 'files/dictionary.xml'
):
    """ extract relations from BTS couchdb dump ZIP file and insert them
    into AED-TEI XML file.
    """
    process_vocab(
        SourceDef(inputfile, 'aaew_wlist'),
        TargetDef(xmlfile, 'entry'),
        PropertyExtraction(
            [bts.get_relations],
            [_verify_relations, _mirror_relations]
        ),
        amendment=PropertyAddition(
            'relations', _has_relation, _add_relation
        ),
    )


def add_lemma_translations(
    inputfile: str = 'dump/vocabulary.zip',
    xmlfile: str = 'files/dictionary.xml'
):
    """ extract translations from BTS couchdb dump ZIP file and insert them
    into AED-TEI XML file.
    """
    process_vocab(
        SourceDef(inputfile, 'aaew_wlist'),
        TargetDef(xmlfile, 'entry'),
        PropertyExtraction(
            [bts.get_translations], None
        ),
        amendment=PropertyAddition(
            'translations', _has_translation, _add_translation
        ),
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

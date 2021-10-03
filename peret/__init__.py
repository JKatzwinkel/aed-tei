"""
Usage:
    peret.py format [ -f FILE ]
    peret.py validate [ -f FILE ]
    peret.py add-translations [ -i FILE ] [ -f FILE ]
    peret.py add-relations [ -i FILE ] [ -f FILE ]
    peret.py add-ths-dateranges [ -i FILE ] [ -f FILE ]

Commands:
    format                  prettify XML file
    validate                validate an AED TEI file against the XML schema in
                            files/aed_schema.xsd

    add-translations        add translations from BTS couchdb dump zip file to
                            AED-TEI XML dictionary file
    add-relations           add relations from BTS couchdb dump zip file to
                            AED-TEI XML dictionary file
    add-ths-dateranges      add dateranges from BTS couchdb dump zip file to
                            AED-TEI XML thesaurus file

Options:
    -f FILE --file FILE     path to local XML file
                            [default: files/dictionary.xml]
    -i FILE --input FILE    path to BTS couchdb dump zip file
                            [default: dump/vocabulary.zip]

"""
from typing import List, Callable

from pathlib import Path

import docopt
from delb import Document  # pylint: disable=import-error
import xmlschema  # pylint: disable=import-error

from peret.proc import (
    SourceDef,
    TargetDef,
    PropertyInsertion,
    PropertyExtraction,
)
from peret.pre import (
    _verify_relations,
    _mirror_relations,
)
from peret.inserters import (
    _get_id,
    _has_relation,
    _add_relation,
    _has_translation,
    _add_translation,
    _has_daterange,
    _add_daterange,
)

from .providers import (
    bts,
)


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
    insertion: PropertyInsertion = None,
):
    """ process entries of AED TEI XML file according to configuration
    and save result to the same XML file.
    """
    print(
        f'add {insertion.property_name} from {src.archive} to {target.xmlfile}'
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
            insertion.property_name, {}
        ).items():
            for value in values:
                if not insertion.has_property(entry, _type, value):
                    insertion.add_property(entry, _type, value)
                    _stats['elements'] += 1
                    _stats['entries'].add(_id)
    print(
        (
            f'added {_stats["elements"]} {insertion.property_name} to '
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
        insertion=PropertyInsertion(
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
        insertion=PropertyInsertion(
            'translations', _has_translation, _add_translation
        ),
    )


def add_ths_dateranges(
    inputfile: str = 'dump/vocabulary.zip',
    xmlfile: str = 'files/thesaurus.xml'
):
    """ extract thesaurus entry dateranges from BTS couchdb dump ZIP file
    and insert them into AED-TEI XML file.
    """
    process_vocab(
        SourceDef(inputfile, 'aaew_ths'),
        TargetDef(xmlfile, 'category'),
        PropertyExtraction(
            [bts.get_ths_entry_dates], None
        ),
        insertion=PropertyInsertion(
            'dates', _has_daterange, _add_daterange,
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
    if args['add-ths-dateranges']:
        add_ths_dateranges(args['--input'], args['--file'])
    if args['validate']:
        validate_file(args['--file'])


if __name__ == '__main__':
    main()

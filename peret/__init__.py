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
    print('initialize registry')
    wlist = src.extract_and_match(target, extraction)
    print('process XML entries')
    _stats = target.update(wlist, insertion)
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
            [bts.get_ths_entry_dates],
            [bts.fill_in_missing_dateranges]
        ),
        insertion=PropertyInsertion(
            'dates', _has_daterange, _add_daterange,
        ),
    )


def prettify_file(filename: str):
    """ format XML file.
    """
    file = Path(filename)
    if not file.exists():
        print(f'XML file {filename} could not be found.')
        return
    Document(file).save(file, pretty=True)


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

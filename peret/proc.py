""" BTS to AED ETL workflow config containers
"""
from __future__ import annotations
import dataclasses
from pathlib import Path
from typing import Callable, Iterable, List

from delb import Document, TagNode

from .providers import bts
from .inserters import _get_id


def patch_vocab(vocab: dict, functions: List[Callable] = None) -> dict:
    """ iterate through all key value pairs in vocab registry and apply one or more
    functions to each.

    >>> from .pre import _verify_relations, _mirror_relations
    >>> wlist = {'1': {'relations': {'root': ['3']}},
    ... '2': {'relations': {'rootOf': ['1']}}}
    >>> patch_vocab(wlist, [_verify_relations, _mirror_relations])['1']
    {'relations': {'root': ['2']}}

    """
    for _id, entry in vocab.items():
        for func in functions:
            vocab[_id] = func(_id, entry, vocab)
    return vocab


@dataclasses.dataclass
class SourceDef:
    """ location of a BTS couchdb dump source vocabulary.
    """
    archive: str = 'dump/vocabulary.zip'
    vocab: str = 'aaew_wlist'

    def extract_and_match(
        self, target: TargetDef, extraction: PropertyExtraction
    ) -> dict:
        """ create and populate a data source entry registry by applying
        extraction and patch functions to all entries in a BTS couchdb dump
        data file that can be matched to an entry in the AED TEI target file.

        >>> wlist = SourceDef('test/dump/vocabulary.zip').extract_and_match(
        ...     TargetDef('files/dictionary.xml'),
        ...     PropertyExtraction(
        ...         [bts.get_translations],
        ...     )
        ... )
        >>> wlist['1']['translations']
        {'de': ['Geier; Vogel (allg.)'], 'en': ['vulture; bird (gen.)']}

        """
        xml_ids = target.get_ids()
        return {
            _id: entry
            for _id, entry in patch_vocab(
                {
                    _id: entry
                    for _id, entry in bts.init_vocab(
                        filename=self.archive,
                        vocab=self.vocab,
                        functions=extraction.extract_funcs or []
                    ).items()
                    if _id in xml_ids
                },
                functions=extraction.patch_funcs or []
            ).items()
            if _id in xml_ids
        }


@dataclasses.dataclass
class PropertyExtraction:
    """ define how properties get extracted from BTS data source and processed
    before inserting them into an AED target model.
    """
    extract_funcs: list[Callable[dict, dict]]
    patch_funcs: list[Callable[str, dict, dict, dict]] = None


@dataclasses.dataclass
class PropertyInsertion:
    """ define a source registry property to be added to target nodes,
    and the functions used to determine whether it already exists and
    to insert it if not.
    """
    property_name: str
    has_property: Callable[TagNode, str, str, bool]
    add_property: Callable[TagNode, str, str, TagNode]


@dataclasses.dataclass
class TargetDef:
    """ definition of XML elements to be updated with the results
    of a data extraction/transformation.

    >>> t = TargetDef()
    >>> t._doc.root.local_name
    'TEI'

    """
    xmlfile: str = 'files/dictionary.xml'
    element: str = 'entry'
    _doc: Document = dataclasses.field(
        init=False,
    )

    def __post_init__(self):
        self._doc = self._load()

    def _load(self) -> Document:
        """ load XML file into delb Document
        """
        return Document(Path(self.xmlfile))

    def save(self):
        """ save delb Document to target file.
        """
        print(f'save results to {self.xmlfile}')
        self._doc.save(Path(self.xmlfile), pretty=True)

    def get_ids(self) -> set[str]:
        """ return the `xml:id` values of each target element.
        """
        return set(
            map(
                _get_id,
                self.get_elements()
            )
        )

    def get_elements(self) -> Iterable[TagNode]:
        """ produce all the elements of interest in the target XML document
        """
        yield from self._doc.css_select(self.element)

    def update(self, entries: dict, insertion: PropertyInsertion) -> dict:
        """ go through AED document entries and apply insertion function to
        add property from BTS data source registry, if applicable.
        return update statistics.
        """
        _stats = {'entries': set(), 'elements': 0}
        for entry in self.get_elements():
            _id = _get_id(entry)
            for _type, values in entries.get(_id, {}).get(
                insertion.property_name, {}
            ).items():
                for value in values:
                    if not insertion.has_property(entry, _type, value):
                        insertion.add_property(entry, _type, value)
                        _stats['elements'] += 1
                        _stats['entries'].add(_id)
        return _stats

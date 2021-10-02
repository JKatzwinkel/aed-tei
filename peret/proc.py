""" BTS to AED ETL workflow config containers
"""
from __future__ import annotations
import dataclasses
from pathlib import Path
from typing import Callable, Iterable

from delb import Document, TagNode

from .inserters import _get_id


@dataclasses.dataclass
class SourceDef:
    """ location of a BTS couchdb dump source vocabulary.
    """
    archive: str = 'dump/vocabulary.zip'
    vocab: str = 'aaew_wlist'


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
class PropertyExtraction:
    """ define how properties get extracted from BTS data source and processed
    before inserting them into an AED target model.
    """
    extract_funcs: list[Callable[dict, dict]]
    patch_funcs: list[Callable[str, dict, dict, dict]]


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

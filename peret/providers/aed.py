""" AED HTML data provider functions
"""
from typing import Iterable

import os
import re
from zipfile import ZipFile

import lxml
import requests
from delb import Document, TagNode  # pylint: disable=import-error

RE_LEMMA_ID = re.compile(r'^[0-9]+$')
RE_HTML_BODY = re.compile(r'<body>.*<\/body>', flags=re.DOTALL)
LENIENT_PARSER = lxml.etree.XMLParser(recover=True)


def pprint(node: TagNode):
    """ pretty print delb tagnode.
    """
    print(
        lxml.etree.tostring(
            node._etree_obj, pretty_print=True
        ).decode()
    )


def _is_lemma_file(path: str) -> bool:
    """ determine whether a path points to an AED lemma HTML file.

    >>> _is_lemma_file('aed-gh-pages/')
    False

    >>> _is_lemma_file('aed-gh-pages/Z3.html')
    False

    >>> _is_lemma_file('aed-gh-pages/89500.html')
    True

    """
    filename = os.path.basename(path)
    if not filename:
        return False
    name, ext = os.path.splitext(filename)
    if ext != '.html':
        return False
    return RE_LEMMA_ID.match(name) is not None


def _load_lemma_dom(html: str) -> Document:
    """ extract `<body>` element from AED lemma HTML and load it into
    delb Document.

    >>> str(_load_lemma_dom('<html><head/><body><p/></body></html>'))
    '<body><p/></body>'

    """
    return Document(
        RE_HTML_BODY.findall(
            html.replace('\n', '')
        )[0],
        parser=LENIENT_PARSER
    )


def dl_aed_lemma_html(lemma_id: str) -> Document:
    """ load AED lemma HTML body into a delb Document.

    >>> lemma = dl_aed_lemma_html('89500')
    >>> len(lemma.css_select('p.most_relevant_occurrences > .transcription'))
    5
    >>> str(list(
    ...     lemma.css_select('.main_information > .tooltip')[0].child_nodes()
    ... )[0])
    '• töten'

    """
    return _load_lemma_dom(
        requests.get(
            'https://raw.githubusercontent.com/simondschweitzer/'
            f'aed/gh-pages/{lemma_id}.html'
        ).text
    )


def load_lemmata(
    filename: str = 'dump/gh-pages.zip',
    num: int = 0
) -> Iterable[Document]:
    """
    load AED HTML lemmata representations from ZIP file (only the `<body>`
    elements tho). Maximum number of lemmata might be capped using `num`
    parameter.

    >>> fn = 'test/dump/gh-pages.zip'
    >>> len(list(load_lemmata(filename=fn, num=10)))
    10

    >>> list(load_lemmata(filename=fn, num=1))[0].root.local_name
    'body'

    """
    with ZipFile(filename) as zip_file:
        for i, lemmafile in enumerate(
            filter(
                _is_lemma_file,
                zip_file.namelist()
            )
        ):
            if i+1 > num > 0:
                break
            with zip_file.open(lemmafile) as file:
                html = str(file.read())
            yield _load_lemma_dom(html)

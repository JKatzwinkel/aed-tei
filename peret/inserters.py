""" functions for inserting properties into AED files.
"""
from delb import (  # pylint: disable=unused-import # noqa: F401
    Document,
    TagNode,
    tag,
)


XML_NS = "http://www.w3.org/XML/1998/namespace"
DATERANGE_BOUNDS = {
    'beginning': 'from',
    'end': 'to'
}


# pylint: disable=invalid-name
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
        entry.attributes.get(f'{{{XML_NS}}}id')
    )

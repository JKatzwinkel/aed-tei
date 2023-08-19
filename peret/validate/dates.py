from pathlib import Path

from delb import (
    Document,
    TagNode,
    QueryResults,
)

from peret.inserters import _strip_id, XML_NS


def get_dates(filename: str = 'files/thesaurus.xml') -> QueryResults:
    """
    >>> len(get_dates('test/files/thesaurus.xml'))
    65
    """
    return Document(
        Path(filename)
    ).css_select('category').filtered_by(
        lambda e: e.css_select('category > catDesc > date').size > 0
    )


def select_date(xml_id: str, filename: str = 'files/thesaurus.xml') -> TagNode:
    '''

    >>> isinstance(select_date('tlaDUVGWT7GSRCKDM5LFTGU6MZ3GY', 'test/files/thesaurus.xml'), TagNode)
    True

    '''
    directory = {
        node['{http://www.w3.org/XML/1998/namespace}id']: node
        for node in get_dates(filename)
    }
    return directory.get(xml_id)


def daterange(node: TagNode) -> tuple:
    """

    >>> daterange(select_date('tlaD3R5CH5NZBDA7IZMCKKJPWYZKU', 'test/files/thesaurus.xml'))
    (0, 0)

    >>> daterange(select_date('tla7FUWX6PWFJDAXEWQDOAA4FYXFU', 'test/files/thesaurus.xml'))
    (-5500, -3151)

    """
    return tuple(
        map(
            int,
            [
                node.css_select('category > catDesc > date')[0].attributes.get(
                    boundary
                ) for boundary in ['from', 'to']
            ]
        )
    )


def get_date_dict(node: TagNode) -> dict:
    """ returns a dict-representation of an XML node describing a thesaurus entry of type date.
    It contains the following attributes:

    - id: BTS ID
    - name: thesaurus entry default label
    - daterange: date range of the thesaurus entry itself
    - contains: cumulative date range of the entries descendants

    >>> # pylint: disable=line-too-long
    >>> get_date_dict(get_dates('test/files/thesaurus.xml')[-4])
    {'id': 'IT24BFWQQ5FL7NSNEPBYN3JUQA', 'name': 'Wadj / Ita', 'daterange': [-2968, -2956], 'contains': [-2968, -2956]}
    """
    return {
        'id': _strip_id(node.attributes[f'{{{XML_NS}}}id']),
        'name': node.xpath('./catDesc')[0].full_text,
        'daterange': list(daterange(node)),
        'contains': list(child_range(node)),
    }


def child_range(node: TagNode) -> tuple:
    """
    >>> child_range(get_dates('test/files/thesaurus.xml')[1])
    (-600, 0)

    >>> child_range(select_date('tlaDUVGWT7GSRCKDM5LFTGU6MZ3GY', 'test/files/thesaurus.xml'))
    (-5500, 0)

    """
    children = node.xpath('./category')
    if children.size > 0:
        ranges = list(map(
            child_range, children
        )) + [daterange(node)]
        start, end = [
            agg(
                daterange[i] for daterange in ranges
            )
            for i, agg in enumerate((min, max))
        ]
    else:
        start, end = daterange(node)
    return (start, end)


def is_valid(node: TagNode) -> bool:
    """
    >>> dates = get_dates('test/files/thesaurus.xml')

    >>> is_valid(dates[1])
    False

    >>> is_valid(dates[2])
    True

    """
    own_daterange = daterange(node)
    rec_daterange = child_range(node)
    return own_daterange[0] <= rec_daterange[0] <=\
        rec_daterange[1] <= own_daterange[1] and \
        abs(own_daterange[0] * own_daterange[1]) > 0


def find_invalid(filename: str = 'files/thesaurus.xml') -> QueryResults:
    """
    >>> get_date_dict(find_invalid('test/files/thesaurus.xml')[2])['name']
    '(Epochen und Dynastien)'

    """
    return get_dates(filename).filtered_by(lambda n: not is_valid(n))

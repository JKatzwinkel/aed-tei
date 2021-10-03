""" data source provider functions for extending AED TEI files.
"""


def register_qualified_property(
    registry: dict, qualifier: str, value: str
) -> dict:
    """ add a value to the list stored under the accompaning qualifier.

    >>> register_qualified_property({}, 'k', 'v')
    {'k': ['v']}

    >>> register_qualified_property({}, 'k', None)
    {}

    """
    if qualifier and value:
        registry[qualifier] = registry.get(qualifier, []) + [value]
    return registry

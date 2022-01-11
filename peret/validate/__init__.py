"""
Usage:
    shemu ths-dates [ -i FILE ] [ -t FORMAT ]

Commands:
    ths-dates                   list thesaurus entries with invalid date ranges

Options:
    -i FILE --input FILE        path to AED-TEI XML file
                                [default: files/thesaurus.xml]
    -t FORMAT --to FORMAT       output format
                                [default: csv]

"""
from typing import Iterable
import docopt

from peret.validate.dates import find_invalid, get_date_dict


def _to_csv(dates: Iterable[dict]) -> str:
    """ format collection of date dict representations to CSV.

    >>> _to_csv([{
    ...     'id': '123',
    ...     'name': 'Pepi I.',
    ...     'daterange': [-400, -330],
    ...     'contains': [-400, -330],
    ... }])
    # ID, name, start, end, descendants_start, descendants_end
    123, Pepi I., -400, -330, -400, -330
    """
    rows = [
        ', '.join(
            map(
                str, [date['id'], date['name'], *date['daterange'], *date['contains']]
            )
        )
        for date in dates
    ]
    print(
        '\n'.join(
            [
                '# ID, name, start, end, descendants_start, descendants_end'
            ] + rows
        )
    )


def print_invalid_dateranges(filename: str, output_format: str):
    """ find thesaurus entries with invalid date ranges in XML file
    and print them in the specified format.
    """
    if output_format.strip().lower() not in ('csv', 'txt', 'json'):
        raise ValueError(f'unknown output format "{output_format}"!')
    func = globals().get(f'_to_{output_format}')
    if func is None:
        raise NotImplementedError(f'output format "{output_format}" currently not supported')
    func(
        map(get_date_dict, find_invalid(filename))
    )


def main():
    args = docopt.docopt(__doc__)
    if args['ths-dates']:
        print_invalid_dateranges(args['--input'], args['--to'])


if __name__ == '__main__':
    main()

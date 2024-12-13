import json
import operator
from pathlib import Path

import pytest

from diacea.experiments import (
    convert_to_relative,
    csp_solver,
    graph_based_approach,
    quadtree_approach,
    rule_based_approach,
)


@pytest.mark.parametrize(
    'algorithm',
    [
        convert_to_relative,
        rule_based_approach,
        csp_solver,
        quadtree_approach,
        graph_based_approach,
    ],
)
def test_convert_to_relative(algorithm):
    pth = Path(__file__).parent / 'data/excalidraw.json'
    excalidraw_data = json.loads(pth.read_text())

    relative_data = sorted(
        algorithm(excalidraw_data['elements']),
        key=operator.itemgetter('id'),
    )

    expected_output = sorted(
        [
            {
                'id': 'R3tckAe0ed5CKf6cwsUAo',
                'type': 'rectangle',
                'label': 'Left Box',
                'parent': 'MAZsWO29K5cvfd9zM9Oam',
            },
            {
                'id': 'Bq7ET4JQ_zEgLTXFm4Qht',
                'type': 'rectangle',
                'label': 'Right\nBox',
                'parent': 'MAZsWO29K5cvfd9zM9Oam',
            },
            {
                'id': 'OFfwVnor5iXq8Olhl1tcA',
                'type': 'arrow',
                'label': '',
                'from': 'R3tckAe0ed5CKf6cwsUAo',
                'to': 'Bq7ET4JQ_zEgLTXFm4Qht',
            },
            {
                'id': 'MAZsWO29K5cvfd9zM9Oam',
                'type': 'rectangle',
                'label': 'Moat',
                'parent': '',
            },
        ],
        key=operator.itemgetter('id'),
    )
    assert relative_data == expected_output

import copy
import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_nobroker_response():
    path = Path(__file__).parent.parent / "data" / "spike" / "nobroker-sample-response.json"
    with open(path) as f:
        return json.load(f)

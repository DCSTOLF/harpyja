"""Shape/type contract tests for server.types (Wave 3: AC5).

Wave 3 adds a `degraded` confidence value for the Scout fallback states; the
existing high/medium/low values keep their meaning.
"""

from typing import get_args

from harpyja.server.types import Confidence


def test_confidence_includes_degraded():
    # Wave 3 degrade states 2/3 set confidence="degraded".
    assert "degraded" in get_args(Confidence)


def test_confidence_keeps_wave2_values():
    # Additive change: the prior values must survive.
    assert {"high", "medium", "low"} <= set(get_args(Confidence))

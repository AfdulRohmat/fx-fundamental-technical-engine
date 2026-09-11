from __future__ import annotations

from fx_fundamental_technical.ridge import ridge_fit


def test_nonnegative_constraint_removes_negative_slope() -> None:
    coefficients = ridge_fit(
        [[1.0, 0.0], [1.0, 1.0], [1.0, 2.0]],
        [2.0, 1.0, 0.0],
        penalty=0.1,
        unpenalized=frozenset({0}),
        nonnegative=frozenset({1}),
    )

    assert coefficients[1] == 0.0

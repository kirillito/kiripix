"""A padded Grid (ticket 0127): the strip has no Source pixels."""

import numpy as np
import pytest

from kiripix.ops import Grid, alpha_by_vote, mask_to_source, mask_to_target, sample_nearest, target_centre


def test_a_padded_grid_samples_transparent_cells_and_refuses_them_as_click_targets() -> None:
    source = np.full((8, 10, 4), 255, dtype=np.uint8)
    grid = Grid.uniform(2, 0, 0, 10, 8).padded_to(7, 5)
    assert (grid.width, grid.height, grid.pad_right, grid.pad_bottom) == (7, 5, 2, 1)
    fitted = sample_nearest(source, grid)
    assert fitted.shape == (5, 7, 4)
    assert (fitted[:4, :5] == 255).all() and (fitted[4:] == 0).all() and (fitted[:, 5:] == 0).all()
    assert (alpha_by_vote(fitted, source, grid) == fitted).all()
    assert target_centre(grid, 4, 3) == (9.0, 7.0)
    with pytest.raises(ValueError, match="padded"):
        target_centre(grid, 5, 0)
    assert not mask_to_target(np.ones((8, 10), dtype=np.bool_), grid)[:, 5:].any()
    assert not mask_to_source(np.ones((5, 7), dtype=np.bool_), grid, 10, 8)[:, 10:].any()
    assert Grid.from_json(grid.to_json()) == grid
    old = grid.to_json()
    del old["pad_right"], old["pad_bottom"]
    assert Grid.from_json(old).pad_right == 0

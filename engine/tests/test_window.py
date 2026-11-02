import itertools

import pytest

from codesense.chunking.window import window_ranges


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        (1, 1, [(1, 1)]),
        (1, 40, [(1, 40)]),  # exactly one window
        (1, 41, [(1, 40), (31, 41)]),
        (1, 100, [(1, 40), (31, 70), (61, 100)]),
        (1, 70, [(1, 40), (31, 70)]),  # last window ends exactly at the end: no extra window
        (11, 60, [(11, 50), (41, 60)]),  # ranges can start anywhere (gaps between symbols)
    ],
)
def test_windows_of_40_with_overlap_10(
    first: int, last: int, expected: list[tuple[int, int]]
) -> None:
    assert window_ranges(first, last, size=40, overlap=10) == expected


def test_zero_overlap_tiles_the_range() -> None:
    assert window_ranges(1, 80, size=40, overlap=0) == [(1, 40), (41, 80)]


def test_empty_range_has_no_windows() -> None:
    assert window_ranges(5, 4, size=40, overlap=10) == []


@pytest.mark.parametrize("last", range(1, 200, 7))
def test_windows_cover_every_line_and_overlap_consecutively(last: int) -> None:
    windows = window_ranges(1, last, size=40, overlap=10)

    covered = {line for start, end in windows for line in range(start, end + 1)}
    assert covered == set(range(1, last + 1))
    for (_, previous_end), (start, end) in itertools.pairwise(windows):
        assert start == previous_end - 10 + 1  # shares exactly `overlap` lines
        assert end > previous_end  # every window adds new lines: no window inside another

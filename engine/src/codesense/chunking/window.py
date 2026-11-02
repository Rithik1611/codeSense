"""Fixed-size line windows: the fallback for code outside any symbol, and the Level 3 baseline."""


def window_ranges(first: int, last: int, size: int, overlap: int) -> list[tuple[int, int]]:
    """Inclusive line ranges covering ``first..last``; neighbours share ``overlap`` lines.

    Overlap gives code that straddles a boundary a second chance to appear whole.
    Requires ``0 <= overlap < size`` (checked by IndexConfig), or the loop would not advance.
    """
    ranges: list[tuple[int, int]] = []
    start = first
    while start <= last:
        end = min(start + size - 1, last)
        ranges.append((start, end))
        if end == last:  # stop here: a further window would lie inside this one
            break
        start += size - overlap
    return ranges

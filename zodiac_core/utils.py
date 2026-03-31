def strtobool(val: str) -> bool:
    """Convert a string representation of truth to True or False.

    True values are: y, yes, t, true, on, 1
    False values are: n, no, f, false, off, 0

    Raises ValueError for anything else.

    Drop-in replacement for the removed ``distutils.util.strtobool``
    (removed in Python 3.13), returning ``bool`` instead of ``int``.

    Based on: https://github.com/python/cpython/blob/3.11/Lib/distutils/util.py
    """
    val = val.strip().lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    if val in ("n", "no", "f", "false", "off", "0"):
        return False
    raise ValueError(f"invalid truth value {val!r}")

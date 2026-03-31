# Utilities

Small helper functions that don't belong to any specific module.

## strtobool

Drop-in replacement for `distutils.util.strtobool`, which was removed in Python 3.13.

```python
from zodiac_core.utils import strtobool

strtobool("true")   # True
strtobool("false")  # False
strtobool("yes")    # True
strtobool("no")     # False
```

::: zodiac_core.utils.strtobool
    options:
      heading_level: 3
      show_root_heading: true

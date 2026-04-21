<!-- TOC -->
- [Standard Library](#standard-library)
  - [Math](#math)
  - [Ranges](#ranges)
  - [Date/Time](#datetime)
  - [Strings](#strings)
  - [Math (expanded)](#math-expanded)
  - [Type casting in expressions](#type-casting-in-expressions)
<!-- /TOC -->

## Standard Library

```python
from relationalai.semantics import std
from relationalai.semantics.std import math
from relationalai.semantics.std.datetime import datetime       # Note: shadows Python's datetime
from relationalai.semantics.std import datetime as dt
from relationalai.semantics.std.strings import string, concat
# If you also need Python's datetime: import datetime as py_datetime
```

### Math

```python
math.abs(Qi.column - Qj.column)   # Absolute value (use instead of Python abs())
```

### Ranges

```python
std.common.range(n)                     # 0 to n-1
std.common.range(start, end)            # start to end-1
std.common.range(start, end + 1)        # start to end (inclusive)
```

### Date/Time

```python
# Extract date components
datetime.year(Order.order_ts)            # Year from datetime
datetime.month(Order.order_ts)           # Month from datetime
dt.date.year(CalendarDay.id)             # Year from date
dt.date.month(CalendarDay.id)            # Month from date
dt.date.quarter(CalendarDay.id)          # Quarter from date

# Conversions
dt.datetime.to_date(Order.order_ts)      # DateTime → Date

# Formatting
datetime.format(Order.order_ts, "Y-mm")  # Format to string

# Duration
dt.date.period_days(date1, date2)                    # Days between dates
datetime.period_milliseconds(ts1, ts2)               # Milliseconds between datetimes

# Type casting for comparison
rai.Date(LineItem.ship_date) < rai.Date(LineItem.commit_date)
rai.Date(Order.date) == rai.Date(CalendarDay.id)
```

### Strings

```python
from relationalai.semantics.std.strings import string, concat
from relationalai.semantics.std import strings

# Convert to string (for concatenation with non-string types)
concat(string(FiscalYear.id), "-Q", string(CalendarQuarter.nr))
```

**Full string library** (`from relationalai.semantics.std import strings`):

| Function | Returns | Description |
|----------|---------|-------------|
| `strings.string(x)` | `String` | Convert Number/Float/Date/DateTime to string |
| `strings.concat(s1, s2, *sn)` | `String` | Concatenate 2+ strings |
| `strings.len(s)` | `Integer` | String length |
| `strings.lower(s)` | `String` | Lowercase |
| `strings.upper(s)` | `String` | Uppercase |
| `strings.strip(s)` | `String` | Trim leading/trailing whitespace |
| `strings.replace(s, old, new)` | `String` | Replace substring |
| `strings.substring(s, start, stop)` | `String` | 0-based, stop exclusive |
| `strings.split_part(s, sep, index)` | `String` | 0-based index into split result |
| `strings.split(s, sep)` | `(index, part)` | Returns tuple — enumerate all parts |
| `strings.join(strs, sep="")` | `String` | Join sequence of strings |
| `strings.contains(s, substr)` | constraint | True if s contains substr |
| `strings.startswith(s, prefix)` | constraint | True if s starts with prefix |
| `strings.endswith(s, suffix)` | constraint | True if s ends with suffix |
| `strings.like(s, pattern)` | constraint | SQL LIKE (`%` wildcard, `_` single char) |
| `strings.regex_match(value, regex)` | constraint | Regex match (arg order: value first, regex second) |
| `strings.levenshtein(s1, s2)` | `Integer` | Edit distance (new in v1) |

**Regex module** (`from relationalai.semantics.std import re`):

```python
# Match from start of string — returns RegexMatch with .start(), .end(), .span(), .match
re.match(r"^order_\d+", Order.code)

# Full string match (like ^pattern$)
re.fullmatch(r"[A-Z]{3}-\d{4}", Product.sku, pos=0)
```

<!-- TODO: re.search(), re.findall(), re.sub() exist but raise NotImplementedError in v1 -->
<!-- TODO: RegexMatch.group() and .group_by_name() not yet implemented -->

### Math (expanded)

Beyond `math.abs()`, the v1 math library includes:

```python
from relationalai.semantics.std import math

# Trigonometric (inputs in radians)
math.sin(x), math.cos(x), math.tan(x)
math.asin(x), math.acos(x), math.atan(x)
math.degrees(x), math.radians(x)

# Hyperbolic
math.sinh(x), math.cosh(x), math.tanh(x)

# Exponential / logarithmic
math.exp(x), math.log(x), math.log2(x), math.log10(x), math.natural_log(x)
math.pow(base, exp), math.sqrt(x), math.cbrt(x)

# Rounding / bounds
math.ceil(x), math.floor(x), math.clip(x, lo, hi), math.sign(x)
math.minimum(x, y), math.maximum(x, y)

# Other
math.factorial(n), math.erf(x), math.erfinv(x)
math.isclose(a, b), math.isinf(x), math.isnan(x)
```

**Geographic — `math.haversine()`:**

```python
# Haversine distance — inputs must be in RADIANS
# radius defaults to 1.0 (unit sphere); use 6371 for km, 3959 for miles
math.haversine(math.radians(loc1.lat), math.radians(loc1.lon),
               math.radians(loc2.lat), math.radians(loc2.lon), radius=6371)
```

<!-- TODO: haversine is defined in v1 stdlib but end-to-end engine translation is unverified (test suite has TODO). Validate after solver implementation is complete. -->

### Type casting in expressions

```python
# Explicit type casts for RAI expressions
rai.Float(1.2) + (avg_price - Product.price) / avg_price * rai.Float(1.5)
rai.Number.size(38, 4)(0.0)  # Decimal is deprecated — use Number.size(p, s)
rai.String("VIP").alias("segment")    # String literal in select
```

For the `|` default/fallback operator (SQL COALESCE equivalent) and if-then-else chains, see `rai-pyrel-coding/expression-rules.md` > `|` operator.

**Python builtins do NOT work on RAI expressions.** These are symbolic, not numeric:
- `abs()` -- use `math.abs()`
- `min()`, `max()` -- use `min`/`max` from `relationalai.semantics` (aggregation) or algebraic equivalents
- `round()`, `floor()`, `ceil()` -- use algebraic equivalents or std library

---

<!-- TOC -->
- [Complete Import Catalog](#complete-import-catalog)
  - [Module Alias](#module-alias)
  - [Explicit Imports](#explicit-imports)
  - [Reasoner-Specific Imports](#reasoner-specific-imports)
  - [Standard Library](#standard-library)
  - [Builtin Shadowing](#builtin-shadowing)
<!-- /TOC -->

## Complete Import Catalog

### Module Alias

```python
# Module alias (preferred in reference KGs for conciseness)
import relationalai.semantics as rai
# Then use: rai.Model, rai.Concept, rai.Property; model.where(), model.select(), model.define(), etc.
```

### Explicit Imports

```python
# Explicit imports (preferred in standalone scripts / solver code)
from relationalai.semantics import (
    Model,                              # Model creation
    Float, Integer, String, Date,       # Type references
    DateTime, Number,                   # DateTime for timestamps, Number.size(p,s) for decimals
    sum, count, max, min, avg,          # Aggregation — shadows Python builtins (see note below)
    per, where, select, define,         # Query/definition functions
    require,                            # Constraint creation (also model.require)
    data, distinct,                     # Data loading, dedup
)
```

### Reasoner-Specific Imports

```python
# Reasoner-specific imports
from relationalai.semantics.reasoners.prescriptive import (
    Problem,
    all_different, implies, special_ordered_set_type_1, special_ordered_set_type_2,
)
from relationalai.semantics.reasoners.graph import Graph
```

### Standard Library

```python
# Standard library
from relationalai.semantics import std
from relationalai.semantics.std.datetime import datetime       # datetime.year(), .month(), etc. — shadows Python datetime
from relationalai.semantics.std import datetime as dt           # dt.date.period_days(), dt.datetime.to_date()
from relationalai.semantics.std import math                     # math.abs()
from relationalai.semantics.std.strings import string, concat   # string conversion, concatenation
from relationalai.semantics.std import strings                  # full string library
from relationalai.semantics.std import re                       # regex module (v1)
```

### Builtin Shadowing

```python
# Builtin shadowing — when you need both RAI and Python builtins, use a module alias:
from relationalai.semantics.std import aggregates as aggs       # aggs.sum, aggs.count, aggs.max, aggs.min
import datetime as py_datetime                                  # Python stdlib datetime
```

**Long import lines:** Split across multiple lines with `()` or use `import relationalai.semantics as rai` to keep lines manageable.

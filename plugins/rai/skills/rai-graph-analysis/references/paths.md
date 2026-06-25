# Path Enumeration
<!-- v1-SENSITIVE -->

> **PREVIEW — requires `relationalai>=1.15`** (earlier releases gate multi-edge, repeat-with-dst, point queries, and native filters).

Path enumeration answers questions where **the answer is the route itself** — the actual sequence of nodes and edges along each path — not a node-level metric or an endpoint pair. It operates natively over the ontology (no `Graph()` instance).

## When paths — and when not

Plain enumeration is necessary but not sufficient reason to reach for paths: a recursive query can list routes too. Paths earns its keep when the answer is the route **and** a per-path predicate or metric quantifies over the whole sequence.

| Need | Use |
|------|-----|
| All transitively reachable `(src, dst)` pairs | `graph.reachable()` — no per-path materialization |
| Shortest distance between pairs | `graph.distance()` |
| Per-entity counts / one-hop group-by | `aggregates.count(distinct(...)).per(...)` |
| Fixed-length chain endpoints (k-hop) | Native chain: `Person.follows.follows.name` |
| Variable-length traversal, just the node/edge sequence | `m.path(Concept.rel.repeat(min, max)).all_paths()` |
| **Score/rank each route by a per-node value aggregated *along the sequence*** (not expressible via `reachable`/`distance`; the value is often a reasoner output) | `path(...).all_paths()` + `aggregates.sum(Node(p.nodes).value).per(p)` |
| **Routes satisfying a joint per-path predicate** (every node of / no node of a type; total weight ≤ budget) | `path(...).all_paths()` + per-node predicate on `p.nodes(idx)` |
| **Paths between typed endpoints, node-filtered** | `path(src_typed, edge.repeat(1, N), dst_typed).all_paths()` + in-PyRel per-node predicate |
| **Route alternating between different relationship types** (e.g. `ships_to` then `supplies`, repeated) | `path(a.rel1, b.rel2).repeat(1, 5).all_paths()` — distinct edges in series (`>=1.15`) |
| **Maximal (longest non-extendable) paths** | `path(...).all_paths()`, then in pandas drop any node sequence that is a contiguous sub-chain of a longer one |

## Quick API

```python
# path() / model.path() builds a PathPattern; .all_paths() enumerates all matching
# paths, returning a unary relationship of PathTraversal. Bind with a walrus in where():
df = model.where(
    p := model.path(Concept.edge.repeat(1, 5)).all_paths(),
).select(p, p.nodes["index"], Concept(p.nodes).id.alias("node")).to_df()
```

- **`.repeat(min, max)`** on the edge chain: `repeat(3)` → exactly 3; `repeat(1, 20)` → between 1 and 20; `repeat(0, K)` valid; `repeat(min=1)` raises (a finite `max` is always required). **Pass both bounds explicitly:** on `>=1.15` a bare `repeat(max=20)` defaults `min` to 1, but an upcoming release will require an explicit `min` (it raises), so `repeat(1, 20)` is the form correct on both.
- **`PathTraversal.length`** is a plain property (no parens). A path of hop-length `L` has nodes at indices `0..L`; interior indices are `0 < idx < p.length`.
- **Node/edge access has two distinct shapes:**
  - *Projection in `select(...)`*: `p.nodes["index"]` (position column); `Concept(p.nodes).property` (cast node to a concept, project a property).
  - *Constraint in `where(...)`*: `p.nodes(idx)` with `idx = Integer.ref()` unifies the node at a position. A free `idx` ranges over **all** positions (endpoints included); bound it with `idx > 0, idx < p.length` for interior-only. The endpoints are auto-unified at `p.nodes(0)` and `p.nodes(p.length)`, so you can reference them in an enclosing `where()` / `select()` / `define()` — e.g. `where(p := path(src, ..., dst).all_paths(), src.id < dst.id)`.
  - Same dual shape for `p.relationships(index)` (the edge label at each hop, a `String` — see the format note in the multi-relationship section) and `p.relationship_fields(index, field_index)` (**entity-typed** auxiliary field values of N-arity edges; non-entity fields are not retrievable this way).
- **Not implemented (raise `NotImplementedError`)** — do not teach: `shortest_paths()` (and `.per()`), `reverse()`, `undirected()`. Walk-semantics `all_paths()` is the only mode.
- **Gated (raise on build)** — also do not teach: multi-step chains `A.b.c` (write the hops as separate edges — see multi-relationship sequence below), relationship-field *filtering* (access is fine; read the field and filter in standard PyRel), aggregate expressions inside a path `.where()`, path unions, and unary relationships *as edge arguments*. Adjacent *bare* node arguments compile but yield trivial single-node results — don't use them.
- **On `relationalai>=1.15`,** `all_paths()` unifies the path src/dst with your endpoints, and multi-edge, repeat-with-dst, point queries, and node/endpoint `.where` filters translate natively (no longer slow post-filters). A single `.where` filter may reference only one node, or the two endpoints of one edge; anything spanning multiple edges stays a residual post-filter. **One hard rule:** an N-arity edge's *first* field is the src and its *last* field is the dst — **both must be entity-typed**; a non-entity last field raises `PathEdgeLabelError` (see escalation below).

## Constructor patterns

**(a) Default — a single binary relationship**, direct or derived. When the traversal runs over an intermediary/interaction concept (one with two relationships to the same node type), derive a binary edge between the endpoints and traverse it:

```python
# Intermediary `Interaction` has .source and .target, both to Node.
Node.linked = model.Relationship(f"{Node} linked to {Node}", short_name="linked")
i = Interaction.ref(); a, b = Node.ref(), Node.ref()
model.where(i.source(a), i.target(b)).define(a.linked(b))
df = model.where(p := model.path(Node.linked.repeat(1, 6)).all_paths()) \
          .select(p, p.nodes["index"], Node(p.nodes).id.alias("node")).to_df()
```

**(b) Escalation — a higher-arity edge**, only when the intermediary's identity or attributes must be recovered *along* the path. Derive an arity-≥3 relationship. Currently, **the first field is src and the last field is dst**, and both must be entity-typed (not an `Integer`, `String`, etc.). Other (auxiliary) fields that are **entity-typed** can be read back with `relationship_fields`; non-entity auxiliary fields are not retrievable this way — read them with a separate query on the intermediary concept:

```python
# {Node:src} via {Via:v} reaches {Node:dst} — first/last fields (src, dst) are entities.
# `Via` is entity-typed, so `v` is recovered per hop via relationship_fields (not an
# endpoint). A non-entity last field raises PathEdgeLabelError.
Node.reaches = model.Relationship(f"{Node:src} via {Via:v} reaches {Node:dst}", short_name="reaches")
model.where(...).define(Node.reaches(src, v, dst))
m.path(seed, Node.reaches.repeat(1, 3), ...)  # `v` via p.relationship_fields(idx, 1)
```

Don't reach for the N-arity form by default — the binary derived edge covers the common case.

**(c) Multi-relationship sequence — distinct edges in series** (`relationalai>=1.15`). When a route alternates between different relationships, pass them as separate edge arguments; consecutive edges share the node between them — e.g. `b` is the destination of the first `ships_to` edge and the source of the second `supplies` edge below:

```python
# a route that takes a `ships_to` edge then a `supplies` edge
a, b = Node.ref(), Node.ref()
p := model.path(a.ships_to, b.supplies).all_paths()          # one of each, in series
p := model.path(a.ships_to, b.supplies).repeat(1, 5).all_paths()  # the pair, alternating up to 5×
```

Write multiple hops of the *same* relationship as `repeat` (`Node.r.repeat(1, N)`), never as a multi-step chain `Node.r.r` (gated); write a route over *different* relationships as a multi-relationship sequence like this, and `.repeat(...)` the whole pattern to alternate the pair.

**Edge-label format (`p.relationships`):** on `>=1.15` the per-hop label is a decorated string like `-⟨ships_to⟩→`; strip the decoration to recover the bare relationship name. An upcoming release returns the bare name directly, making the strip unnecessary.

## Per-path aggregation

**Aggregate a per-node / per-edge value *along the route*** to score or rank paths. `reachable`/`distance` discard the sequence, so this isn't expressible through them; the per-node value is often an upstream reasoner output (a centrality score, a prediction, a solved flow) a recursive query cannot compute.

```python
from relationalai.semantics.std import aggregates  # import the aggregates once
p := model.path(SrcType.ref(), Node.linked.repeat(1, N), DstType.ref()).all_paths()
# rank routes by total Node.value summed across the sequence
aggregates.sum(Node(p.nodes).value).per(p)
```

Path-level rollups (`aggregates.count(p).per(...)`, `aggregates.sum(p, p.length).per(...)`) group by the path or its endpoints. Prefer in-PyRel aggregation with `.inspect()`; reserve `.to_df()` + pandas for rollups PyRel can't express (e.g. string-joining node names into a chain label). **Do not** use the design-proposal `global_shortest` / `per_x` forms — they depend on the unimplemented `shortest_paths().per()`.

## Where to express path constraints

Constraints can go in three places. **Prefer the earliest one that fits** — it prunes during enumeration rather than after.

**1. In the path pattern (most preferred) — node types.** Pass `Concept` / `Ref` args to type the endpoints:

```python
src, dst = SrcType.ref(), DstType.ref()
p := model.path(src, Node.linked.repeat(1, N), dst).all_paths()   # start is SrcType, end is DstType
```

**2. In an attached `.where()` — one node, or the two endpoints of one edge.** Filters here translate natively into enumeration:

```python
a, b = Node.ref(), Node.ref()
model.path(a.ships_to, b.supplies).where(SrcType(a)).all_paths()                # node type (prefer form 1)
model.path(a.ships_to, b.supplies).where(b.location == "Seattle").all_paths()   # single-node property
model.path(a.ships_to, b.supplies).where(a.id < b.id).all_paths()               # one edge's two endpoints
```

A single attached filter may reference only one node, or one edge's two endpoints; anything wider goes in the enclosing `where()`.

**3. In the enclosing `where()` — `src` / `dst`, whole-path, and per-node filters.** Bind the path with a walrus, then constrain. `src` / `dst` are auto-unified at `p.nodes(0)` / `p.nodes(p.length)`:

```python
src, dst = SrcType.ref(), DstType.ref()
idx = Integer.ref()
p := model.path(src, Node.linked.repeat(1, N), dst).all_paths()
model.where(p, src.location == "Seattle", dst.location == "London")   # independent src/dst (prefer form 1)
model.where(p, src.id < dst.id)                                        # joint src/dst
model.where(p, p.length == 7)                                          # whole-path property
model.where(p, Flagged(p.nodes(idx)))                                  # ANY node flagged (existential)
model.where(p, not_(where(Flagged(p.nodes(idx)))))                     # NO node flagged (universal)
model.where(p, Node(p.nodes(p.length - 1)).location == "New York")     # a node at a position
```

A free `idx` ranges over **all** positions, endpoints included; add `idx > 0, idx < p.length` for interior-only. **Existential vs universal is the trap:** `where(p, <pred on p.nodes(idx)>)` matches paths where *some* node satisfies the predicate — wrap the whole thing in `not_(where(...))` to mean *every* node. (Model a flag as a `String` or subconcept, not a Boolean.) A universal "only-through-unflagged" route is more efficient pushed into an attached `.where()` on a nested segment:

```python
p := model.path(src, model.path(Node.linked).where(Node.flag == "no").repeat(1, N), dst) \
          .where(dst.flag == "no").all_paths()
```

**Point queries** pin a specific src/dst by id: `where(p, src.id == "X", dst.id == "Y")`. (Relationship-field *filtering* stays gated — read the field with `relationship_fields` and filter in standard PyRel.)

## Walk vs simple path — a routine decision, not an edge case

`all_paths()` has **walk semantics** and there is no native simple-path mode.

- **On a DAG** (BOM, dependency, supply graphs), walks already equal simple paths — nothing to do, no blowup. If you're unsure the graph is acyclic, test it with `Graph.is_acyclic()`.
- **On a cyclic graph** (most networks once backup/bidirectional/feedback links exist), it revisits nodes. Cap `repeat` with a finite `max`, and if node-repetition isn't wanted, **filter to simple paths in PyRel** — drop any path with a repeated node via a negated existential over positions:
  ```python
  i, j = Integer.ref(), Integer.ref()
  simple = model.where(p, not_(where(i < j, p.nodes(i) == p.nodes(j))))
  ```

Decide this consciously every time. State the intent as a business condition ("a route that does not revisit a node"). Simple-path filtering is post-processing — it drops walks after enumeration, so it doesn't reduce enumeration cost; cap `repeat` for that.

## Classifying and saving paths

`PathTraversal` is a first-class concept — attach relationships/properties to flag, classify, and query paths like any entity:

```python
critical_paths = model.Relationship(f"{PathTraversal:p} is a critical path", short_name="critical_paths")
model.where(p := model.path(...).all_paths(), <predicate over p>).define(critical_paths(p))
```

Also bind a path back onto a concept: `Concept.route = model.Relationship(f"{Concept} has {PathTraversal}")` then `.define(x.route(p))`.

## Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Enumeration blows up / runs forever | Walk semantics + cycles → exponential expansion | On a DAG enumeration is finite. Otherwise cap `repeat(min, max)`, narrow with native node/endpoint `.where()` filters, and check `count(p)` before materializing. Simple-path dedup is post-processing — it doesn't curb enumeration cost |
| Using paths where `reachable()` would do | Reaching for paths for plain connectivity | If the answer is "is X reachable" or "all reachable pairs," use `graph.reachable()` |
| `.where()` on a relationship field doesn't work | Relationship-field *filtering* is gated; only node / endpoint filters translate | Read the field with `relationship_fields` and filter in standard PyRel |
| `Chain.repeat(N)` vs `path(...).repeat(N)` give different answers | Edge-repeat constrains only the source; pattern-repeat constrains every interior node | `C.r.repeat(3)` → only source is `C`; `path(C.r).repeat(3)` → every interior is `C` |
| N-arity edge raises `PathEdgeLabelError` | Paths need the edge's first field to be the src entity and last to be the dst entity | Order the relationship so entities are first and last; entity-typed auxiliary fields (in the middle) read via `relationship_fields`, non-entity ones via a separate query on the intermediary |
| Selecting `p.length` alongside `p.nodes` fans out rows (known issue, fix in progress) | The node rows get duplicated per length value | Project nodes only; query `p.length` separately |
| Integer columns error in pandas | Graph/index columns arrive as `Int128` | Cast `.astype(int)` before pandas math/grouping |

## Cross-link

Graph-level questions (centrality, community, components) still go through `Graph()` — see [algorithm-selection.md](algorithm-selection.md). Paths sits alongside it and may consume a `Graph()` output (e.g. a centrality score) as the per-node value it aggregates along a route.

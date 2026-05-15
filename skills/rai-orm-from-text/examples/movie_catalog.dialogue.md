# movie_catalog — CSDP Dialogue

The canonical small example for rai-orm-from-text. Shows CSDP Steps 0–7 on a small movie-catalog domain. Domain-neutral concept names; the pattern maps to any catalog-style domain (books, recipes, songs, etc.).

Step counts and turn numbers are illustrative — a real CSDP run might cover the same content in fewer or more turns depending on user response density.

---

**Step 0 — Mode opener**

`Claude:` *I can run CSDP in Guided or One-shot mode. Guided walks through the seven steps in conversation; One-shot drafts in one pass from a description. Which would you prefer?*

`User:` Guided.

**Step 1 — Elementary facts**

`Claude:` *Great. To start, can you walk me through a typical instance from your domain? A movie row, a sample form, or just describe one concrete movie.*

`User:` Sure. Movie ID 1, "The Departed", directed by Martin Scorsese, released in 2006, rated R. Movie ID 2, "Inception", directed by Christopher Nolan, released 2010, rated PG-13. Movie ID 3, "Parasite", directed by Bong Joon-ho, 2019, rated R.

`Claude:` *Thanks — three examples is enough for the population check. Let me decompose into elementary facts and verbalize each. Please confirm, correct, or reject:*
- *'Movie #1 has title "The Departed".' Is this an atomic fact in your domain?*
- *'Movie #1 directed by Director "Martin Scorsese".' Is this atomic?*
- *'Movie #1 released in Year 2006.' Atomic?*
- *'Movie #1 has rating R.' Atomic?*

`User:` All four are atomic. We treat title, director, release year, and rating as independent facts per movie.

`Claude:` *Got it. Now reference-scheme elicitation:*
- *How is each Movie identified — by movie-id, by title, by something else?*
- *How is each Director identified — by name, by an ID?*
- *Year is an integer; rating is a string with restricted values. Both are value types, not entity types. Is that right?*

`User:` Movie is identified by movie-id (we generate them on creation). Director is identified by name — we don't have a separate ID system for them; we treat full name as the identifier and accept that duplicate names are a real edge case we handle manually. Year is just an integer. Rating uses MPAA: G, PG, PG-13, R, NC-17 — those are the only allowed values.

`Claude:` *Recording:*
- *Movie — reference mode `popular`, value type `MovieId` (Integer).*
- *Director — reference mode `general`, value type `DirectorName` (String).*
- *Year — value type, Integer primitive.*
- *Rating — value type with an enum constraint at Step 6 (will propose `{G, PG, PG-13, R, NC-17}`).*

*Confirm and continue?*

`User:` Confirm.

**Step 2 — Fact types and population check**

`Claude:` *I've drawn the fact types and populated them with your examples. Let me re-verbalize for the population check:*

```
Movie has title:
  Movie #1 → 'The Departed'
  Movie #2 → 'Inception'
  Movie #3 → 'Parasite'

Movie directed-by Director:
  Movie #1 → Martin Scorsese
  Movie #2 → Christopher Nolan
  Movie #3 → Bong Joon-ho

Movie released-in Year:
  Movie #1 → 2006
  Movie #2 → 2010
  Movie #3 → 2019

Movie has-rating Rating:
  Movie #1 → R
  Movie #2 → PG-13
  Movie #3 → R
```

*Anything missing or wrong in the populations?*

`User:` Looks right.

**Step 3 — Combine entity types / arithmetic derivations**

`Claude:` *Walking the model: I see Movie and Director as distinct entity types. Year and Rating as value types. No obvious merges. Any computed facts in your domain? (e.g., 'age = current_year - release_year' that you'd want stored as a derived fact?)*

`User:` Not for v1 — we just store the release year.

**Step 4 — Uniqueness constraints**

`Claude:` *For each fact type:*

*Movie has title — in your sample, each Movie has exactly one title. Is that always true, or can a Movie have multiple titles (translations, alternative titles)?*

`User:` Each Movie has one canonical title in our catalog. We may store translations separately later, but for v1 it's one title per Movie.

`Claude:` *Got it — Movie role is unique on `Movie has title`. Confirmed.*

*Movie directed-by Director — each Movie has one Director in your sample. Always true, or co-directors allowed?*

`User:` We pick one director for co-directed films. So yes, one Director per Movie.

`Claude:` *Movie role unique. Confirmed.*

*Are Directors unique per movie or can two Movies have the same Director?*

`User:` Same Director can direct many Movies. So Director isn't unique.

`Claude:` *So the fact type is m:1 — Movie role unique, Director role not. Confirmed.*

*Movie released-in Year — each Movie has one release year. Confirmed?*

`User:` Yes.

*Movie has-rating Rating — each Movie has one rating. Confirmed?*

`User:` Yes.

**Step 5 — Mandatory role constraints**

`Claude:` *For each role, is participation required?*

*Is every Movie required to have a title?*

`User:` Yes.

`Claude:` *Mandatory on Movie role of `Movie has title`. Confirmed.*

*Is every Movie required to have a Director?*

`User:` Yes. We don't catalog Movies without a director credit.

`Claude:` *Mandatory. Confirmed.*

*Released in Year — required?*

`User:` Required.

*Rating — required?*

`User:` Required.

**Step 6 — Value, set-comparison, ring, subtyping**

`Claude:` *I have three constraint proposals from the library and one from LLM inference. Want me to surface them now (6d spot-check), or defer all to Step 7?*

`User:` Surface them now.

`Claude:` *Proposed constraints:*

*1. Value enumeration on Rating (from sample populations):*
*   `Rating allowed: ['R', 'PG-13']` — but you mentioned the full MPAA set is `{G, PG, PG-13, R, NC-17}`. Should I use the full MPAA set as the value constraint, or the sample-observed subset?*

`User:` Use the full MPAA set. The sample is small.

`Claude:` *Updated: `Rating allowed: ['G', 'PG', 'PG-13', 'R', 'NC-17']`, source: explicit, status: confirmed.*

*2. Value range on Year (from sample populations + LLM inference): `Year between 1888 and current_year`. The 1888 lower bound is from "the first known movie was made in 1888"; the upper bound is the current year. Confirm?*

`User:` Yes for the lower bound. The upper bound: use 2100 as a far-future cap rather than current_year — easier to reason about and we may catalog upcoming-release movies.

`Claude:` *Updated: `Year between 1888 and 2100`. source: llm-inferred for the 1888 lower bound; source: user-supplied for the 2100 upper bound.*

*3. The library proposes a uniqueness constraint on `(Director, Year)` for `Movie directed-by Director`: "the same Director doesn't typically direct two movies in the same year." This is a soft heuristic — does it hold in your domain?*

`User:` No, Soderbergh directed two movies in 2018 (Logan Lucky and Unsane were 2017/2018... actually he's done several). Reject.

`Claude:` *Rejected. Moving the proposal to `rejected_proposals` so we don't re-propose.*

*No ring constraints (no self-referential fact types). No subtype proposals — Movie and Director don't show evidence of role-distinct subtypes.*

**Step 7 — Final review and commit**

`Claude:` *Whole-model verbalization for review:*

```
=== Object Types ===

Movie is identified by MovieId.
Director is identified by DirectorName.
Year is a value of type Integer.
Rating is a value of type String.

=== Fact Types ===

Movie has title String. [from user, confirmed]
Each Movie has exactly one title.

Movie directed-by Director. [from user, confirmed]
Each Movie is directed by exactly one Director.

Movie released-in Year. [from user, confirmed]
Each Movie was released in exactly one Year.

Movie has-rating Rating. [from user, confirmed]
Each Movie has exactly one Rating.

=== Top-level Constraints ===

[from user, confirmed] Rating ∈ {'G', 'PG', 'PG-13', 'R', 'NC-17'}.
[from LLM + user, confirmed] Year between 1888 and 2100.

=== Antipattern Flags ===

(none)

=== Rejected Proposals ===

[from common-sense library, rejected] Same Director can't direct two movies in the same year. (Reason: counter-example given by user.)
```

*Modality questions: every constraint is currently labelled `alethic`. Any you want to mark `deontic`?*

`User:` All alethic.

`Claude:` *Final review: anything you want to add (Step 7d — user-supplied constraints) or change?*

`User:` Nothing to add. Looks good.

**Step 7f — Commit**

`Claude:` *Committed. Three files emitted:*
- *`movie_catalog.orm.yaml` — full model.*
- *`movie_catalog.verbalization.txt` — CNL rendering.*
- *`movie_catalog.py` — PyRel translation (Step 8 ran automatically; review the deontic-note section if any).*

*Summary: 1 entity type + 1 entity type-as-value-of-other-fact + 2 value types, 4 fact types, 6 constraints. No deontic, no antipatterns.*

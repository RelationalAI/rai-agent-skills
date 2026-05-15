# library_with_subtypes — CSDP Dialogue (subtype check)

Demonstrates CSDP Step 6's subtype check on a library-catalog domain. Shows the Halpin role-based criterion in action: a user-proposed subtype is rejected because the differences are attribute-based, not role-based. A different subtype is accepted because it has a real role difference.

**Setup:** the user has provided Step 1–5 content (elementary facts, populations, uniqueness, mandatory) for a library catalog. Step 6 begins.

---

**Step 6 — subtype check (turn 28 onwards)**

`Claude:` *Walking the model for subtype proposals. From your descriptions:*
- *You mentioned 'BookItem' and 'PeriodicalItem' as distinct kinds of LibraryItem.*
- *You mentioned 'Reference book' vs 'Circulating book' as a distinction.*

*Let me apply the ORM 2 subtype criterion: a subtype is justified only when its instances play roles the supertype doesn't. Let me check each:*

*Proposal A: BookItem and PeriodicalItem as subtypes of LibraryItem.*

*Does a BookItem play any roles a generic LibraryItem doesn't?*

`User:` Yes. BookItem has an author and a publisher. PeriodicalItem has an issue-number and a publication-date (not a publisher in the same way — it has a publishing house but it varies by issue).

`Claude:` *Got it. So:*
- *BookItem has-author Author. PeriodicalItem doesn't.*
- *PeriodicalItem has-issue-number Integer. BookItem doesn't.*

*Role differences are real → BookItem and PeriodicalItem are justified subtypes. Confirmed.*

*Proposal B: Reference book vs Circulating book as subtypes of BookItem.*

*Does a Reference book play any roles a generic BookItem doesn't?*

`User:` Mmm, kind of. Reference books can't be checked out — Circulating books can. So 'checked-out-by Patron' applies to Circulating books only.

`Claude:` *Wait — let me push back. Is "checked-out-by Patron" a role that BookItem can play (some of them) but Reference books are simply prevented from? Or is it structurally different — i.e., the schema would not even allow a Reference book to play that role?*

`User:` Hmm. Actually the schema allows it — the constraint is "you can't check out a Reference book" but the data structure is the same. We enforce it in policy.

`Claude:` *Then the difference is a value constraint, not a role difference:*
- *Both Reference and Circulating books can play the role 'has-type BookType'.*
- *Both can play 'has-author Author', 'has-title Title', etc.*
- *The "can be checked out" distinction is captured by an `is_reference: Boolean` flag or by a `book_type: Reference | Circulating` value constraint, plus a separate policy rule.*

*The Halpin posture would say: don't introduce Reference/Circulating as subtypes. Add `book_type` as a value of BookItem (enum constraint), and emit a separate constraint:*

```
[deontic]
A BookItem with book_type='Reference' should not be checked out.
```

*The 'should not' phrasing is deliberately deontic — your policy enforces it, but the schema doesn't structurally prevent it. Is that closer to how your domain actually works?*

`User:` Yes, that's exactly it. We enforce the no-checkout policy in the application layer, not in the data model. I was confusing 'distinct categories in our world' with 'distinct subtypes in the model'.

`Claude:` *Common confusion — this is what the Halpin role-based criterion catches. Updating the model:*
- *Reject Reference/Circulating subtype proposal.*
- *Add BookType value type with enum `{'Reference', 'Circulating'}`.*
- *Add deontic constraint at Step 7d (user-supplied): "A BookItem with book_type='Reference' should not be checked out."*

*Continuing to other Step 6 proposals...*

---

**Outcome:**
- BookItem and PeriodicalItem confirmed as subtypes (role-based justification: different has-* fact types).
- Reference vs Circulating rejected as subtypes; replaced with a `BookType` value enumeration + a deontic policy constraint.

This dialogue snippet is the kind of move CSDP makes possible that ER-flavored modeling rarely catches — the "I have two categories, must I create two subtypes?" question gets resolved by checking for role differences rather than attribute differences.

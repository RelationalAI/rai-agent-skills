# objectification_in_enrollment — CSDP Dialogue (when to objectify)

Demonstrates CSDP recognizing when a binary fact type should be objectified (turned into an entity in its own right). Classic ORM 2 pattern: `Student enrolled-in Course` becomes `Enrolment` once we discover the relationship itself has attributes (grade, enrolled-at).

---

**Step 1 — Elementary facts (turn 1–8)**

`User:` I want to model student course enrollment. Students can take courses. Each enrollment has a grade and a date.

`Claude:` *Let me verbalize the elementary facts:*
- *'Student enrolled-in Course.' — atomic?*
- *'<something> has grade Grade.' — atomic, but I need to know what gets the grade. The student? The course? The enrollment?*
- *'<something> happened on Date.' — same question, what gets the date?*

`User:` The grade is per enrollment — each student gets a separate grade per course. The date is when the enrollment happened, also per enrollment.

`Claude:` *That's a strong signal that "enrollment" is more than just a relationship — it's an entity that has its own attributes. In Halpin's terminology this is **objectification**: the Student-enrolled-in-Course relationship is objectified as an Enrolment entity. Let me re-verbalize:*

- *'Student enrolled-in Course.' (Underlying binary fact type, objectified.)*
- *'Enrolment has grade Grade.' (Atomic fact on the objectification.)*
- *'Enrolment occurred-on Date.' (Atomic fact on the objectification.)*

*Is this how you'd describe it?*

`User:` Yes — that captures it. We treat enrollment as its own thing.

`Claude:` *Reference scheme: how is each Enrolment identified?*

`User:` By the combination of Student and Course — a Student can only enroll in a given Course once per term, but actually we re-use the same Enrolment if they re-take it. So Student+Course is enough to uniquely identify.

`Claude:` *That's a composite identifier — Halpin's `external` reference mode. The two reference-bearing fact types are 'Enrolment for Student' and 'Enrolment for Course' (the underlying binary, decomposed into the objectification's reference structure). I'll mark the objectification as **independent** because an Enrolment can exist before it has a grade (you mentioned the grade is set during the course, not at enrollment time).*

`User:` Right.

---

**Step 4 — Uniqueness (turn 19–22)**

`Claude:` *For the objectified fact types:*

*Enrolment for Student → each Enrolment is for exactly one Student, but a Student can have many Enrolments. Confirmed?*

`User:` Confirmed.

*Enrolment for Course → each Enrolment is for exactly one Course, but a Course can have many Enrolments. Confirmed?*

`User:` Confirmed.

*External UC: the combination (Student, Course) is unique per Enrolment. Confirmed?*

`User:` Confirmed.

---

**Step 6 — Constraints (turn 32–40)**

`Claude:` *Library hits:*

*Grade is a value type. Common library entries for grades: enum like 'A | B | C | D | F | I | W'. Use that, or a different convention?*

`User:` Use the standard A-F + I (incomplete) + W (withdrawn). Confirmed enum.

*Date for "occurred-on": library proposes `>= 1900-01-01` (date-contemporary entry). For Enrolment timestamps, a tighter bound would be the institution's founding date. Want me to propose that?*

`User:` We were founded in 1955. Use 1955-01-01.

`Claude:` *Updated. source: user-supplied for the 1955 lower bound; source: common-sense for the upper bound (no upper bound — open above).*

*No ring constraints (no self-referential fact types in this model). No further subtype proposals.*

---

**Outcome:**
- `Student enrolled-in Course` is recognized as the underlying binary fact type.
- `Enrolment` is emitted as an entity type with `reference: { mode: external }`, `objectification_independent: true`.
- Two reference-bearing fact types (`enrolment_for_student`, `enrolment_for_course`) emit the composite identifier.
- Attribute fact types on the objectification: `enrolment_has_grade`, `enrolment_occurred_on`.
- External UC across the two reference-bearing fact types.

This is the canonical objectification pattern in Halpin's framework. New users often try to model this as "Enrolment has-student Student, Enrolment has-course Course, Enrolment has-grade Grade" without recognizing that Enrolment **IS** the objectified relationship — not just an entity that happens to reference both. The CSDP dialogue surfaces this by asking "what gets the grade?" — and the answer (the enrollment, not the student or course) forces the user to name the objectification explicitly.

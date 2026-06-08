# Conference talk tracking — initial domain description

> **What this file is.** A clean seed input for the rai-orm-from-text flow. The skill's CSDP dialogue extends this through Discuss-phase elicitation; the final ORM model lives at `evals/expected/synthetic_good_user.orm.yaml`. The full reference dialogue is in [`dialogue.md`](dialogue.md) — *that* is the eval fixture; *this* is the input a real user would seed.

We track academic and industry conferences. Each **conference** has multiple **tracks** (for example, "ML Track" or "Systems Track" at DataConf 2026). Each track schedules **talks** in slot order — a talk like "Embeddings at Scale" might be the third talk in the ML Track.

Each talk is given by a **speaker**. Typically one speaker per talk; occasionally a talk is co-presented by two. We need to record who gives each talk.

We need to know, for any given talk: which conference it's part of, which track it belongs to, and its slot position within that track. Two talks in the same track cannot share a slot.

Talks are typically capped at 60 minutes, though this is a soft preference rather than a hard rule (a keynote may run longer with prior agreement). Keynotes are recognized by their role at the event, not as a separate kind of entity.

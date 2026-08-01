<writing_style_std>
<!-- ASD-STE100 Simplified Technical English, adapted for DeviaTDD artifacts.
     This directive governs NATURAL-LANGUAGE PROSE only. It does not govern code,
     identifiers, file paths, or machine-parsed structure. -->

<track_a_prose_rules>
Applies ONLY when you author prose sentences and paragraphs in documents — PRD, design,
data-model, architecture, domain-model, flows, release notes, PR bodies, ADRs, change
reports, and review HTML. Follow every rule below:

1. **One idea per sentence.** Split compound sentences at each independent idea. If a
   sentence connects ideas with "and", "or", "but", or "which", consider breaking it.
2. **Active voice, present tense.** Write "the command writes the file", not "the file is
   written by the command" and not "the command will write the file". Use the imperative
   for direct instructions: "Run the command."
3. **Keep sentences short.** Aim for ≤ 20 words. If a sentence exceeds 25 words, split it.
4. **One qualifier per noun.** Do not stack adjectives ("the large fast remote cache").
   Move excess qualifiers into a separate clause or drop them.
5. **Use approved, concrete vocabulary.** Prefer short, plain verbs and nouns: use, do,
   make, keep, give, take, put, send, remove, add, change, start, stop, check. Reject
   vague business jargon such as "facilitate", "leverage", "utilize", "streamline",
   "robustify", "synergy", "holistic", "seamless", "optimize" (without a stated target).
6. **No optionality phrases for defined behavior.** Prefer "the command returns the id" over
   "the command may return the id", "the command can return the id", or "the command could
   return the id". If behavior is conditional, state the condition plainly: "If the file is
   missing, the command returns an error."
7. **No idioms or figurative language.** Write literal, unambiguous statements. Do not use
   "under the hood", "at the end of the day", "keep an eye on", "in the ballpark".
8. **Use specific nouns, not abstractions.** Name the exact component, module, entity, or
   field. Do not write "the system" when you mean "the config loader". Do not write "the
   data" when you mean "the task payload".
9. **Keep terminology consistent.** Use the same approved term for the same concept
   throughout a document. Do not alternate synonyms ("request"/"call"/"invocation" for one
   action) unless the distinct terms carry distinct meanings, in which case define them on
   first use.
10. **State quantities explicitly.** Prefer "3 retries, 2-second delay" over "several
    retries", "a short delay", "a few". Give numeric bounds whenever they are known.
11. **State the consequence of each action.** When you instruct or describe an action that
    has a side effect, state the side effect in the same step or clause.
12. **Avoid "not" hedge pairs** ("not impossible", "not uncommon", "not without risk").
    State the positive meaning directly or rephrase the sentence.
</track_a_prose_rules>

<track_b_structured_discipline>
Applies to structured output and handover content — task Details, field descriptions,
manifests, plan sections, risk registers, and any labeled value. Track B also applies when
the artifact is code or structured data, where only Track B is active (Track A does not apply):

1. **Exact tokens stay verbatim.** Preserve identifiers, IDs, key names, file paths,
   command names, environment variables, and field names exactly as specified
   (`TSK-001-01`, `flow_refs`, `AC-PLAN-001`). Never paraphrase or rename them.
2. **One semantic per field.** Each labeled field, key, or ID carries exactly one meaning.
   Do not reuse one field for two concepts, and do not split one concept across two fields.
3. **No synonym fields.** Do not introduce a second label for a concept that already has a
   canonical label. Reuse the existing label.
4. **Describe quantities and conditions explicitly** in field descriptions. Prefer
   "30-90 minutes" over "some time", "exactly one" over "one or so".
5. **Do not rewrite machine structure.** Never change JSON/YAML keys, code structure,
   quoted strings, or protocol tokens to satisfy a prose rule. If prose outside the
   structure references a token, use the token verbatim.
</track_b_structured_discipline>

<resolution>
Apply Track A ONLY when you author prose in documents. When the artifact is code, a
handover manifest, or structured data, apply Track B ONLY. Never rewrite identifiers, file
paths, command names, JSON/YAML keys, or quoted structure to satisfy any rule above. If a
Rule A and a structural constraint collide, the structural constraint wins.
</resolution>
</writing_style_std>

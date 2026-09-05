# UI Contract

Responsibility: provide a minimal execution interface and visual evidence review.

Primary views: Today, Map and Review. Today separates NOW, two NEXT human-focus items, BACKGROUND automation and collapsed LATER work. Primary actions are Start/Pause, Time correction and Finish/Review. Outcome capture uses labelled states and contextual blocker/study inputs.

Advanced structure editing, archive/restore and backup remain available under the overflow menu. Planning is not performed in the UI; AI snapshot/plan controls bridge to ChatGPT.

Guarantees: no icon-only status ambiguity; no horizontal overflow at supported viewports; timer state survives reload; fields do not expand due to timer clicks; computed values are not presented as manually editable facts.

Current limitation: these layout guarantees are specified but await an executed Playwright run. See `KNOWN_ISSUES.md`.

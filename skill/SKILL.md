---
name: historical-sources
description: Use when a claim about the Three Kingdoms era (184-280 CE) or Han China needs a primary source — unit types, offices, place names, people, events, distances, populations. Queries a local index over 1,271 volumes of public-domain Chinese histories (三國志 with 裴松之注, 後漢書 with 續漢書 志, 華陽國志, 晉書, 資治通鑑, 漢書, 史記, 讀史方輿紀要, 三國演義 and more) and returns book, chapter title, and the verbatim passage. Use it INSTEAD of answering from memory, and use it to prove a term is absent before treating it as invented.
---

# Historical Sources — 삼국지 시대 사료 질의

Grounds historical claims in text you can quote. **The point is to make "I don't know"
measurable**: a query returning nothing is evidence of absence, and absence gets reported
as UNKNOWN — never filled in from memory.

## Query

```bash
python3 -m shiliao.index 白馬義從              # everything
python3 -m shiliao.index 突騎 --era            # only sources covering 184-280 CE
python3 -m shiliao.index 連弩 --book 華陽國志
python3 -m shiliao.index 屯長 --book 後漢書 --limit 3
```

Output is `[사서 권 편명] …passage…` with the hit wrapped in 《》. Works at any query
length, including 2-character terms.

`--era` restricts to 三國志 · 後漢書 · 華陽國志 · 晉書 · 資治通鑑 · 三國演義 — the sources
that treat the period directly. Without it you also search 漢書 · 史記 · 隋書 · 魏書 ·
宋書 · 讀史方輿紀要 · 元和郡縣圖志 · 世說新語 and the military/institutional treatises,
which is right for background and geography but will pull in the wrong dynasty for a
question about 220 CE.

Two volume ranges worth knowing: 後漢書 卷109–113 是 **郡國志** (the 105 commanderies with
their county lists) and 卷114–118 是 **百官志** (offices with their salary ranks, including
the 部-曲-屯 military ladder). This edition numbers 續漢書 志 as 後漢書 卷91–120.

## Setup (once, if the index is missing)

```bash
python3 -m shiliao.fetch     # ~20 min → ~/.shiliao (124MB)
python3 -m shiliao.index     # ~1 min  → ~/.shiliao/index.db (85MB)
```

Both resume; re-run to fill gaps. Do not raise `--jobs` above 4 — wikisource returns
empty bodies without erroring.

## Rules

1. **Query before asserting.** Naming a unit, office, county, or polity from memory is
   fabrication until the index confirms it. Claims this index has already overturned:
   「象兵」's only 後漢書 hit is 「或執銅鏡以象兵」 — a verb ("made bronze mirrors look like
   weapons"), not a corps; 「白毦兵」 appears in no volume at all.
2. **Search 繁體.** The corpus is traditional throughout. 簡體 misses silently — 雒阳
   returns nothing, 雒陽 works. This matters when cross-checking against simplified
   datasets like CHGIS.
3. **Read the snippet — matching is character-level, so false positives are real.**
   Querying `屯長` (a Han officer rank) also returns 「西**屯長**安」 — "garrisoned
   Chang'an". Chinese has no word boundaries for the index to see. **A raw hit count is
   not evidence.**
4. **Quote, don't paraphrase.** Carry the passage and its 사서·권·편명 into whatever you
   write, so a reader can check it without re-running the query.
5. **Zero hits ⇒ UNKNOWN.** Say which books were searched and stop. Do not substitute a
   plausible term, and do not quietly soften the claim into something you can support.
6. **Absence here is not absence in the record.** 水經注, 東觀漢記, 太平御覽, 藝文類聚,
   通典 are NOT indexed. Report the boundary rather than declaring the record silent.
7. **Grade sources; never average them.** 正史 and 演義 are separate claims, not one
   blended assertion. When both exist, state both and label which is which.

## Adding a source

Add its title pattern to `titles()` in `shiliao/fetch.py` and its filename prefix to
`BOOK` in `shiliao/index.py`, then re-fetch and re-index. Confirm the exact wikisource
title first — formats are inconsistent across books (`後漢書/卷18` resolves,
`後漢書/卷十八` does not; 讀史方輿紀要 uses Chinese numerals only).

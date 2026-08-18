---
name: historical-sources-ext
description: Use when a Three Kingdoms era question needs a source OUTSIDE the era proper — a place name traced through later geography, an institution's Han precedent, a Northern/Southern dynasty successor account. Queries a bundled index over 588 volumes of public-domain Chinese histories (史記, 宋書, 魏書, 隋書, 讀史方輿紀要) and returns book, chapter title, and the verbatim passage. This is the companion to `historical-sources`, which holds the era proper; query that one first.
---

# Historical Sources (extension) — 시대 밖 사료

`historical-sources` 의 짝이다. 그쪽이 삼국지 시대(184~280)를 직접 다루는 사서를 들고
있고, 여기는 **그 앞뒤와 후대 지리지**를 든다. 질문이 220년 안쪽이면 그쪽을 먼저 쓰고,
여기는 밖을 일부러 볼 때 쓴다.

| 사서 | 권 | 쓰임 |
|---|---|---|
| 史記 | 130 | 한 이전 제도·지명의 유래 |
| 宋書 | 100 | 삼국 이후 남조가 남긴 후속 기록 |
| 魏書 | 120 | 북조 시각의 후속 기록 (北魏 서술) |
| 隋書 | 76 | 經籍志 등 후대 목록·제도 정리 |
| 讀史方輿紀要 | 121 | 명대 역사지리 — 지명 비정의 표준 참고 |

## Query

```bash
python3 -m shiliao.index 白馬                    # 이 번들 전체
python3 -m shiliao.index 江陵 --book 讀史方輿紀要
python3 -m shiliao.index 屯田 --book 史記 --limit 3
```

출력은 `[사서 권 편명] …원문…` 이고 검색어를 《》로 감싼다. 두 글자 질의도 잡힌다.

## Rules

`historical-sources` 의 규칙 일곱 개가 여기에도 그대로 적용된다. 특히 이 번들에서
더 위험한 둘:

- **왕조를 확인해라.** 여기 사서는 삼국지 시대가 아니다. 「白毦」는 이 코퍼스에서
  劉裕(晉·宋 교체기)의 기치로 걸리지 촉의 백이병이 아니다. 권·편명을 보고 시대를 판별한 뒤
  인용해라. 시대를 안 밝히고 옮기면 그게 곧 날조다.
- **여기서 나왔다고 그 시대 근거가 되지 않는다.** 후대 지리지의 비정은 후대의 판단이다.
  「讀史方輿紀要 가 A 를 B 라 한다」로 적고 「A 는 B 다」로 적지 마라.

## 범위 밖

水經注, 東觀漢記, 太平御覽, 藝文類聚, 通典 은 어느 번들에도 없다. 미검출은
「이 코퍼스에서 미검출」이지 「사서에 없음」이 아니다.

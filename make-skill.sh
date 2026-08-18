#!/bin/sh
# claude.ai 에 올릴 스킬 번들을 만든다. 업로드 한도는 압축 해제 기준 30MB 다.
#
# 전권(1,271권) 색인은 41MB 라 한 번들에 안 들어간다. 사서를 버리는 대신 **둘로 나눈다** —
# 스킬은 여러 개 올릴 수 있고, 어차피 두 묶음은 쓰임이 다르다.
#
#   historical-sources      삼국지 시대를 직접 다루는 사서 + 배경·지리 (683권, 20MB)
#   historical-sources-ext  전후 왕조와 후대 지리지 (588권, 20MB)
#
# 쪼갠 선은 왕조다. 220년 인물·제도·병종 질문은 core 로 끝나고, ext 는 「이 지명이
# 후대 지리지에 어떻게 남았나」처럼 일부러 밖을 볼 때 쓴다. 각 SKILL.md 가 자기 범위와
# 상대 번들을 명시한다 — 「여기 없다 ≠ 사서에 없다」가 규칙 6 이기 때문이다.
set -e
CORE='sgz,hhs,hyg,js,js2,zztj,yy,hs,yhjx,ssxy'
EXT='sj,ss,wei,sui,dsfy,misc'
ROOT=$(cd "$(dirname "$0")" && pwd)

bundle() {   # $1=이름 $2=사서목록 $3=SKILL.md경로
    out="$ROOT/dist/$1"
    mkdir -p "$out/corpus" "$out/shiliao"
    cp "$3" "$out/SKILL.md"
    cp "$ROOT/shiliao/"*.py "$out/shiliao/"
    tmp=$(mktemp -d)
    for p in $(echo "$2" | tr ',' ' '); do cp "$ROOT/corpus/$p-"*.txt "$tmp/" 2>/dev/null || true; done
    SHILIAO_HOME="$tmp" python3 -m shiliao.index
    cp "$tmp/index.db" "$out/corpus/index.db"
    rm -rf "$tmp"
    size=$(du -sm "$out" | cut -f1)
    [ "$size" -lt 30 ] || { echo "$1 ${size}MB — 30MB 한도 초과." >&2; exit 1; }
    (cd "$ROOT/dist" && zip -qr "$1.zip" "$1")
    echo "dist/$1 ${size}MB"
}

rm -rf "$ROOT/dist"
mkdir -p "$ROOT/dist"
bundle historical-sources "$CORE" "$ROOT/SKILL.md"
bundle historical-sources-ext "$EXT" "$ROOT/SKILL-ext.md"

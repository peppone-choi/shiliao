#!/usr/bin/env python3
"""zh.wikisource(public domain) 에서 삼국지 시대 사료 코퍼스를 받는다.

받은 원문은 `$SHILIAO_HOME`(기본 `~/.shiliao`)에 떨어진다. 원문은 모두 public domain 이지만
저장소를 사료 배포처로 쓰지 않는다 — 이 스크립트로 언제든 재현되기 때문이다.

주의 두 가지.
  1. urllib 기본 요청은 403 이다. User-Agent 를 반드시 보낸다.
  2. 병렬도를 올리면 위키소스가 **오류 없이 빈 응답**을 준다. 기본 4를 넘기지 말고,
     한 번 더 돌려 빠진 것을 메운다(이미 받은 파일은 건너뛴다).

용법:  python3 -m shiliao.fetch [--jobs 4]
"""
import argparse, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

OUT = os.environ.get('SHILIAO_HOME') or os.path.expanduser('~/.shiliao')
UA = 'shiliao/1.0 (+https://github.com/peppone-choi/shiliao)'

_D = '零一二三四五六七八九'


def cn(n):
    """讀史方輿紀要 는 권을 한자로 매긴다(卷五十). 아라비아 숫자 제목은 없다."""
    if n < 10:
        return _D[n]
    if n < 20:
        return '十' + (_D[n % 10] if n % 10 else '')
    if n < 100:
        return _D[n // 10] + '十' + (_D[n % 10] if n % 10 else '')
    tail = ('' if n % 100 >= 10 else '零') + cn(n % 100) if n % 100 else ''
    return _D[n // 100] + '百' + tail


def titles():
    """(위키소스 제목, 저장 파일명). 제목 형식은 실제로 응답을 확인한 것만 쓴다.

    형식이 사서마다 다르다 — 三國志/史記/漢書 는 3자리 영, 隋書/魏書 는 무영,
    讀史方輿紀要 는 한자. 「後漢書/卷十八」은 없고 「後漢書/卷18」이 있다.
    後漢書 는 이 판본에서 紀10+列傳80 = 卷1~90, 續漢書 志30 = 卷91~120 이라
    郡國志(卷109~113)·百官志(卷114~118)를 권 번호만으로 받을 수 있다.
    """
    # ── 삼국지 시대를 직접 다루는 사서 ──
    for i in range(1, 66):
        yield f'三國志/卷{i:02d}', f'sgz-{i:02d}.txt'          # 裴松之注 포함 = 산일 인용서 200여 종
    for i in range(1, 121):
        yield f'後漢書/卷{i}', f'hhs-{i:03d}.txt'
        yield f'後漢書/卷{i}上', f'hhs-{i:03d}A.txt'
        yield f'後漢書/卷{i}下', f'hhs-{i:03d}B.txt'
    for i in '一 二 三 四 五 六 七 八 九 十 十一 十二'.split():
        yield f'華陽國志/卷{i}', f'hyg-{i}.txt'                 # 파촉·남중의 유일한 당대 지방지
    for i in range(1, 131):
        yield f'晉書/卷{i:03d}', f'js-{i:03d}.txt'
        yield f'晉書/卷{i}', f'js2-{i:03d}.txt'
    for i in range(49, 121):
        yield f'資治通鑑/卷{i:03d}', f'zztj-{i:03d}.txt'        # 편년. 「公元一九一年」이 본문에 있다
    for i in range(1, 121):
        yield f'三國演義/第{i:03d}回', f'yy-{i:03d}.txt'
    # ── 배경·제도·지리 ──
    for i in range(1, 101):
        yield f'漢書/卷{i:03d}', f'hs-{i:03d}.txt'              # 西域傳의 거리·호구·승병 수치
    for i in range(1, 131):
        yield f'史記/卷{i:03d}', f'sj-{i:03d}.txt'
    for i in range(1, 86):
        yield f'隋書/卷{i}', f'sui-{i:03d}.txt'                 # 지리지·경적지
    for i in range(1, 131):
        yield f'魏書/卷{i}', f'wei-{i:03d}.txt'
        yield f'魏書/卷{i}上', f'wei-{i:03d}A.txt'
        yield f'魏書/卷{i}下', f'wei-{i:03d}B.txt'
    for i in range(1, 101):
        yield f'宋書/卷{i}', f'ss-{i:03d}.txt'                  # 州郡志·樂志
    for i in range(1, 41):
        yield f'元和郡縣圖志/卷{i}', f'yhjx-{i:02d}.txt'
    for i in range(1, 131):
        yield f'讀史方輿紀要/卷{cn(i)}', f'dsfy-{i:03d}.txt'     # 역대 지명 고증의 집대성
    for i in ('德行 言語 政事 文學 方正 雅量 識鑒 賞譽 品藻 規箴 捷悟 夙惠 豪爽 容止 自新 企羨 '
              '傷逝 棲逸 賢媛 術解 巧藝 寵禮 任誕 簡傲 排調 輕詆 假譎 黜免 儉嗇 汰侈 忿狷 讒險 '
              '尤悔 紕漏 惑溺 仇隙').split():
        yield f'世說新語/{i}', f'ssxy-{i}.txt'                  # 인물 일화·품평
    # ── 병서·제도서·잡저 ──
    for t in '孫子兵法 六韜 三略 獨斷 西京雜記 博物志 潛夫論 鹽鐵論 釋名 太白陰經'.split():
        yield t, f'misc-{t}.txt'                              # 獨斷(蔡邕) = 후한 제도·의례


def fetch(job):
    title, name = job
    path = os.path.join(OUT, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return None
    url = 'https://zh.wikisource.org/w/index.php?' + urllib.parse.urlencode(
        {'action': 'raw', 'title': title})
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            if not body or body.startswith(b'#REDIRECT'):      # 리다이렉트 문서는 본문이 아니다.
                return None
            with open(path, 'wb') as f:
                f.write(body)
            return name
        except Exception:
            time.sleep(1 + attempt)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=4,
                    help='기본 4. 올리면 위키소스가 조용히 빈 응답을 준다.')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    jobs = list(titles())
    with ThreadPoolExecutor(a.jobs) as ex:
        got = [n for n in ex.map(fetch, jobs) if n]
    have = len([f for f in os.listdir(OUT) if f.endswith('.txt')])
    print(f'요청 {len(jobs)} · 이번에 받음 {len(got)} · 보유 {have}권 → {OUT}', file=sys.stderr)
    if len(got) and have < len(jobs) * 0.4:
        print('빠진 것이 많다. 한 번 더 실행하면 이어받는다.', file=sys.stderr)


if __name__ == '__main__':
    main()

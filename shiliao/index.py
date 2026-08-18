#!/usr/bin/env python3
"""삼국지 시대 사료를 질의 가능한 인덱스로 만든다 — CodeGraph 가 코드에 하는 일을 사료에 한다.

수십 MB 를 매번 grep 하지 않고 `$SHILIAO_HOME/index.db`(SQLite FTS5) 를 한 번 만들어 두면
「어느 사서 어느 편에 이 말이 나오나」를 밀리초에 답한다.

한문은 공백이 없어 기본 토크나이저가 한 권을 토큰 하나로 본다. trigram 토크나이저는
3자 미만 질의를 놓친다(「義從」이 안 잡힌다). 그래서 **글자 사이에 공백을 넣어 색인하고
구(phrase) 질의로 되돌린다** — 길이에 상관없이 정확히 잡힌다.

용법:
    python3 -m shiliao.index                     # 인덱스 생성/갱신
    python3 -m shiliao.index 白馬義從              # 질의
    python3 -m shiliao.index 連弩 --book 華陽國志
    python3 -m shiliao.index 突騎 --era           # 삼국지 시대(184~280) 사서만
"""
import argparse, glob, os, re, sqlite3, sys, zlib

# 레포에 코퍼스가 같이 들어 있다. 클론만 하면 바로 질의된다 — 설정도 다운로드도 없다.
_BUNDLED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'corpus')
HOME = (os.environ.get('SHILIAO_HOME')
        or (_BUNDLED if os.path.isdir(_BUNDLED) else os.path.expanduser('~/.shiliao')))
DB = os.path.join(HOME, 'index.db')

BOOK = {'sgz': '三國志', 'hhs': '後漢書', 'hyg': '華陽國志', 'js': '晉書', 'js2': '晉書',
        'yy': '三國演義', 'zztj': '資治通鑑', 'yhjx': '元和郡縣圖志', 'ssxy': '世說新語',
        'ss': '宋書', 'hs': '漢書', 'sj': '史記', 'sui': '隋書', 'wei': '魏書',
        'dsfy': '讀史方輿紀要', 'misc': '기타'}

# 삼국지 시대(184 황건 ~ 280 오 멸망)를 **직접** 다루는 사서. 나머지는 배경·후대 지리지다.
ERA_BOOKS = {'三國志', '後漢書', '華陽國志', '晉書', '資治通鑑', '三國演義'}

# 續漢書 志는 이 판본에서 後漢書 卷91~120 이다. 郡國志·百官志를 권 번호로 바로 부를 수 있게 한다.
ZHI = {**{i: '郡國志' for i in range(109, 114)}, **{i: '百官志' for i in range(114, 119)}}

SECTION = re.compile(r'\|\s*section\s*=\s*([^\n|}]+)')
NOTES = re.compile(r'\|\s*notes\s*=\s*([^\n|}]+)')
# 판본 품질 틀({{textquality|25%}})은 파이프에서 잘려 「{{textquality」 조각으로 남는다. 편명이 아니다.
JUNK = re.compile(r'\{\{\w*$|^\}*')
NOVEL = re.compile(r'\{\{Novel\|[^|]*\|([^|]+)\|')
YEAR = re.compile(r'公元([一二三四五六七八九十百零〇]+)年')
CN = {c: i for i, c in enumerate('〇一二三四五六七八九')}
CN['零'] = 0

split = lambda s: ' '.join(s)


def cn2int(s):
    """공元一九一年 같은 자릿수 나열과 一百九十一 같은 십진 표기를 모두 읽는다."""
    if '十' not in s and '百' not in s:
        try:
            return int(''.join(str(CN[c]) for c in s))
        except KeyError:
            return None
    n = tot = 0
    for c in s:
        if c in CN:
            n = CN[c]
        elif c == '十':
            tot += (n or 1) * 10; n = 0
        elif c == '百':
            tot += (n or 1) * 100; n = 0
    return tot + n


def clean(s):
    """위키 마크업을 벗겨 사람이 읽을 편명으로 만든다.

    판본 품질 틀 {{textquality|25%}} 은 헤더 파싱이 파이프에서 끊어 「{{textquality」 조각을
    남긴다. 편명이 아니므로 버린다. 권 번호도 vol 이 이미 들고 있어 중복을 지운다.
    """
    s = re.sub(r"\[\[[^\]|]*\|?([^\]]*)\]\]", r'\1', s)
    s = re.sub(r"'''|''|\{\{[^}]*\}\}|__\w+__|&nbsp;|<[^>]+>", '', s)
    s = re.sub(r'\(?\{\{\w*\)?\s*$', '', s.strip())
    s = re.sub(r'^卷[一二三四五六七八九十百]+[·　 ]*', '', s)
    return re.sub(r'[\s　]+', ' ', s).strip(' ·|')


def meta(name, text):
    """(사서, 권, 편명). 편명은 위키 헤더의 section= 이며, 三國志는 notes= 에 입전 인물이 있다."""
    m = re.match(r'([a-z0-9]+?)-(.+)\.txt$', name)
    if not m or m.group(1) not in BOOK:
        return None
    book, num = BOOK[m.group(1)], m.group(2)
    vol = f'卷{num}'
    if book == '後漢書':
        n = int(re.sub(r'\D', '', num) or 0)
        if n in ZHI:
            vol = f'卷{n} {ZHI[n]}'
    head = text[:1200]
    title = ''
    for pat in (NOVEL, SECTION):
        hit = pat.search(head)
        if hit:
            title = clean(hit.group(1)); break
    people = NOTES.search(head)
    if people:
        p = clean(people.group(1))
        if p and len(p) < 90 and not p.startswith('起'):   # 자치통감 notes 는 간지 범위라 편명이 아니다.
            title = f'{title} ({p})' if title else p
    return book, vol, title


def years(text):
    """수록 연도 범위(서기). 자치통감은 「公元一九一年」을 본문에 달고 있어 그대로 읽힌다."""
    ys = [y for y in (cn2int(x) for x in YEAR.findall(text)) if y and 0 < y < 700]
    return (min(ys), max(ys)) if ys else (None, None)


def build(books=None):
    """색인을 만든다. FTS 에는 본문을 **저장하지 않는다**(content='').

    예전 판은 글자분할한 본문을 FTS 가 통째로 한 벌 더 들고 있었다 — 원문 41MB 에
    DB 가 85MB 였던 이유다. 검색에 필요한 건 색인이고 본문은 스니펫에만 쓰이므로,
    본문은 zlib 로 눌러 별도 테이블에 두고 스니펫은 파이썬에서 잘라 낸다.
    """
    os.makedirs(HOME, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(
        'drop table if exists src; drop table if exists vol;'
        'create table vol (book, vol, title, y0, y1, body blob);'
        "create virtual table src using fts5(body, tokenize='unicode61', content='');")
    rows = 0
    for path in sorted(glob.glob(os.path.join(HOME, '*.txt'))):
        name = os.path.basename(path)
        if books and name.split('-')[0] not in books:
            continue
        text = open(path, encoding='utf-8', errors='replace').read()
        m = meta(name, text)
        if not m:
            continue
        y0, y1 = years(text)
        cur = con.execute('insert into vol values (?,?,?,?,?,?)',
                          (m[0], m[1], m[2], y0, y1, zlib.compress(text.encode(), 9)))
        # FTS rowid 를 vol rowid 에 맞춰 둔다 — 조인 없이 바로 되짚는다.
        con.execute('insert into src (rowid, body) values (?,?)', (cur.lastrowid, split(text)))
        rows += 1
    con.commit()
    con.execute('vacuum')
    books_in = [r[0] for r in con.execute('select book from vol')]
    print(f'{rows}권 색인 · {os.path.getsize(DB)/1e6:.0f}MB → {DB}', file=sys.stderr)
    print('  ' + ' · '.join(f'{b}{books_in.count(b)}' for b in sorted(set(books_in))), file=sys.stderr)


def snippet(text, term, pad=26):
    """스니펫을 본문에서 직접 자른다. contentless FTS 는 snippet() 을 못 준다."""
    i = text.find(term)
    if i < 0:
        return text[:pad * 2].replace('\n', ' ')
    a, b = max(0, i - pad), min(len(text), i + len(term) + pad)
    body = text[a:i] + '《' + term + '》' + text[i + len(term):b]
    return ('…' if a else '') + body.replace('\n', ' ') + ('…' if b < len(text) else '')


def search(term, book=None, era=False, limit=10):
    """질의 결과를 [{id, book, vol, title, snippet}] 로 돌려준다. 미검출이면 빈 리스트.

    CLI 도 MCP 서버도 이 함수 하나만 쓴다 — 표면이 갈라지면 규칙도 갈라진다.
    """
    con = sqlite3.connect(DB)
    where, args = ['src match ?'], ['"' + split(term) + '"']
    if book:
        where.append('v.book = ?'); args.append(book)
    if era:
        where.append('v.book in (%s)' % ','.join('?' * len(ERA_BOOKS))); args += sorted(ERA_BOOKS)
    args.append(limit)
    hits = con.execute(
        'select v.rowid, v.book, v.vol, v.title, v.body from src join vol v on v.rowid = src.rowid '
        'where ' + ' and '.join(where) + ' order by rank limit ?', args).fetchall()
    return [{'id': str(r), 'book': b, 'vol': v, 'title': t,
             'snippet': snippet(zlib.decompress(body).decode(), term)}
            for r, b, v, t, body in hits]


def query(term, book, era, limit):
    hits = search(term, book, era, limit)
    if not hits:
        scope = book or ('삼국지 시대 사서' if era else '전체 코퍼스')
        print(f'✗ 「{term}」 — {scope}에서 미검출. 사료 근거 없음(추측으로 채우지 말 것).')
        return
    for h in hits:
        head = f"{h['book']} {h['vol']}" + (f" {h['title']}" if h['title'] else '')
        print(f"[{head}]\n  {h['snippet']}")


def volume(rowid):
    """권 하나의 전문(마크업 제거)."""
    con = sqlite3.connect(DB)
    row = con.execute('select book, vol, title, body from vol where rowid = ?', [rowid]).fetchone()
    if not row:
        return None
    b, v, t, blob = row
    body = zlib.decompress(blob).decode()
    body = re.sub(r'<ref[^>]*>.*?</ref>|<[^>]+>', '', body)
    body = re.sub(r'\{\{[^{}]*\}\}', '', body)          # 교감주·품질틀. 본문이 아니다.
    body = re.sub(r"\[\[[^\]|]*\|?([^\]]*)\]\]", r'\1', body)
    return {'book': b, 'vol': v, 'title': t, 'text': re.sub(r'\n{3,}', '\n\n', body).strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('term', nargs='?', help='없으면 인덱스를 새로 만든다')
    ap.add_argument('--book', help='사서 한정 (三國志·後漢書·華陽國志·晉書·資治通鑑 …)')
    ap.add_argument('--era', action='store_true',
                    help='삼국지 시대(184~280)를 직접 다루는 사서만. 漢書·史記·隋書 등 배경 사서를 뺀다')
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--books', help='색인에 넣을 사서 접두어 쉼표 구분 (예: sgz,hhs,hyg,js,zztj,yy)')
    a = ap.parse_args()
    if not a.term:
        build(set(a.books.split(',')) if a.books else None)
    elif not os.path.exists(DB):
        sys.exit(f'인덱스가 없다({DB}). 인자 없이 먼저 실행해라.')
    else:
        query(a.term, a.book, a.era, a.limit)


if __name__ == '__main__':
    main()

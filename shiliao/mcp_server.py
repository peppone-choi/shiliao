#!/usr/bin/env python3
"""사료 인덱스를 MCP 로 연다 — 클로드·코덱스·제미나이(stdio), 챗GPT(HTTP) 공용.

표준 라이브러리만 쓴다. 네 프로바이더가 전부 MCP 를 말하므로 서버 하나면 통합이 하나다.

    python3 -m shiliao.mcp_server              # stdio  (Claude Code / Codex / Gemini CLI)
    python3 -m shiliao.mcp_server --http 8787            # HTTP   (클로드 웹/앱·챗GPT 커넥터)\n    SHILIAO_TOKEN=... python3 -m shiliao.mcp_server --http 8787 0.0.0.0   # 외부 노출 시
"""
import json, os, sys
from . import index

PROTOCOL = '2025-06-18'

# 도구 설명은 규칙을 나르는 유일한 통로다 — SKILL.md 를 못 읽는 클라이언트도 이건 읽는다.
RULES = ('반드시 인용문을 그대로 옮겨라(요약·의역 금지). 미검출은 「기록 없음」이 아니라 '
         'UNKNOWN 이며, 기억으로 메우지 마라. 질의는 번체 한자로 하고, 매칭이 글자 단위라 '
         '무관한 문장이 걸릴 수 있으니 snippet 을 직접 읽어 확인해라.')

TOOLS = [{
    'name': 'search_sources',
    'description': '삼국지 시대(184~280) 한문 사료 원문을 검색해 사서·권·편명과 원문 인용을 돌려준다. '
                   '용어·인물·제도·지명이 실제로 어느 사서 어디에 적혀 있는지 확인할 때 써라. ' + RULES,
    'inputSchema': {
        'type': 'object',
        'properties': {
            'term': {'type': 'string', 'description': '번체 한자 검색어 (예: 白馬義從, 連弩, 郡國志)'},
            'book': {'type': 'string', 'description': '사서 한정', 'enum': sorted(set(index.BOOK.values()))},
            'era': {'type': 'boolean', 'description': 'true 면 삼국지 시대를 직접 다루는 사서만 '
                                                      '(三國志·後漢書·華陽國志·晉書·資治通鑑·三國演義)'},
            'limit': {'type': 'integer', 'default': 10},
        },
        'required': ['term'],
    },
}, {
    # 챗GPT 의 딥리서치·기업지식 경로는 이 이름과 이 모양(문자열 인자 하나)을 강제한다.
    # 개발자 모드 대화에서는 search_sources 를 그대로 써도 되지만, 한 서버로 양쪽을 덮는다.
    'name': 'search',
    'description': '삼국지 시대 한문 사료에서 검색어가 나오는 권을 찾는다. ' + RULES,
    'inputSchema': {'type': 'object', 'required': ['query'],
                    'properties': {'query': {'type': 'string', 'description': '번체 한자 검색어'}}},
}, {
    'name': 'fetch',
    'description': 'search 가 돌려준 id 의 권 전문을 가져온다.',
    'inputSchema': {'type': 'object', 'required': ['id'],
                    'properties': {'id': {'type': 'string', 'description': 'search 결과의 id'}}},
}]


def head(h):
    return f"{h['book']} {h['vol']}" + (f" {h['title']}" if h['title'] else '')


def oa_search(query):
    """챗GPT 규격 — content[0].text 에 JSON 문자열을 담는다."""
    hits = index.search(query, limit=20)
    return json.dumps({'results': [
        {'id': h['id'], 'title': head(h), 'url': f"shiliao://{h['id']}", 'text': h['snippet']}
        for h in hits]}, ensure_ascii=False)


def oa_fetch(rid):
    v = index.volume(int(rid)) if str(rid).isdigit() else None
    if not v:
        return json.dumps({'error': f'unknown id: {rid}'}, ensure_ascii=False)
    return json.dumps({'id': str(rid), 'title': f"{v['book']} {v['vol']}" + (f" {v['title']}" if v['title'] else ''),
                       'url': f'shiliao://{rid}', 'text': v['text'],
                       'metadata': {'book': v['book'], 'vol': v['vol']}}, ensure_ascii=False)


def call(args):
    if not os.path.exists(index.DB):
        return f'인덱스가 없다({index.DB}). `python3 -m shiliao.fetch && python3 -m shiliao.index` 를 먼저 실행해라.'
    term = args.get('term', '')
    hits = index.search(term, args.get('book'), args.get('era', False), args.get('limit', 10))
    if not hits:
        scope = args.get('book') or ('삼국지 시대 사서' if args.get('era') else '전체 코퍼스')
        return (f'✗ 「{term}」 — {scope}에서 미검출. 사료 근거 없음 = UNKNOWN 으로 보고하고 '
                f'기억으로 채우지 마라. (이 코퍼스에 없다는 뜻이지 사서 전체에 없다는 뜻은 아니다.)')
    return '\n'.join(
        f"[{h['book']} {h['vol']}" + (f" {h['title']}" if h['title'] else '') + f"]\n  {h['snippet']}"
        for h in hits)


def handle(req):
    """JSON-RPC 요청 하나를 처리한다. 알림(id 없음)은 None 을 돌려 응답을 생략한다."""
    m, rid = req.get('method'), req.get('id')
    if m == 'initialize':
        r = {'protocolVersion': PROTOCOL, 'capabilities': {'tools': {}},
             'serverInfo': {'name': 'shiliao', 'version': '1.0.0'},
             'instructions': RULES}
    elif m == 'tools/list':
        r = {'tools': TOOLS}
    elif m == 'tools/call':
        p = req.get('params', {})
        name, a = p.get('name'), p.get('arguments', {})
        if name == 'search_sources':
            text = call(a)
        elif name == 'search':
            text = oa_search(a.get('query', ''))
        elif name == 'fetch':
            text = oa_fetch(a.get('id', ''))
        else:
            return {'jsonrpc': '2.0', 'id': rid,
                    'error': {'code': -32602, 'message': f'unknown tool: {name}'}}
        r = {'content': [{'type': 'text', 'text': text}]}
    elif rid is None:
        return None                       # notifications/initialized 등 — 응답하면 프로토콜 위반이다.
    else:
        return {'jsonrpc': '2.0', 'id': rid, 'error': {'code': -32601, 'message': f'unknown method: {m}'}}
    return {'jsonrpc': '2.0', 'id': rid, 'result': r}


def stdio():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            res = handle(json.loads(line))
        except Exception as e:                                    # noqa: BLE001
            res = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32603, 'message': str(e)}}
        if res is not None:
            print(json.dumps(res, ensure_ascii=False), flush=True)


def http(port, host='127.0.0.1'):
    """Streamable HTTP 전송. 클로드 웹/앱 커넥터·챗GPT 등 stdio 를 못 붙이는 클라이언트용.

    브라우저에서 오는 커넥터는 프리플라이트를 보내고 CORS 를 본다. 공개 주소에 띄우는 순간
    누구나 붙을 수 있으므로 SHILIAO_TOKEN 이 있으면 Bearer 로 막는다 —
    127.0.0.1 밖으로 내보내면서 토큰을 안 걸면 그냥 열어 둔 것이다.
    """
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    token = os.environ.get('SHILIAO_TOKEN')

    class H(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers',
                             'Content-Type, Authorization, Mcp-Session-Id, MCP-Protocol-Version')
            self.send_header('Access-Control-Allow-Methods', 'POST, GET, DELETE, OPTIONS')
            self.send_header('Access-Control-Expose-Headers', 'Mcp-Session-Id')

        def reply(self, code, body=b'', ctype='application/json'):
            self.send_response(code)
            self.cors()
            if body:
                self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_OPTIONS(self):
            self.reply(204)

        def do_GET(self):
            # 서버가 먼저 말을 걸 일이 없어 SSE 스트림을 열지 않는다. 사양상 405 가 정답이다.
            self.reply(405)

        do_DELETE = do_GET

        def do_POST(self):
            # 커넥터 UI 들은 정적 헤더를 넣는 칸이 없다(클로드=OAuth, 제미나이=DCR/자격증명).
            # 그래서 URL 경로로도 같은 토큰을 받는다 — https://…/<token>/ 로 붙이면 된다.
            ok = (self.headers.get('Authorization') == f'Bearer {token}'
                  or self.path.strip('/').split('/')[0] == token)
            if token and not ok:
                self.reply(401, b'{"error":"unauthorized"}'); return
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            try:
                res = handle(json.loads(body))
            except Exception as e:                                # noqa: BLE001
                res = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32603, 'message': str(e)}}
            if res is None:
                self.reply(202); return
            out = json.dumps(res, ensure_ascii=False)
            # 사양상 JSON 한 방으로 끝내도 되지만, event-stream 만 받겠다는 클라이언트가 있다.
            # 프레임 하나로 감싸 주면 같은 응답이 양쪽에서 다 읽힌다.
            acc = self.headers.get('Accept', '')
            if 'text/event-stream' in acc and 'application/json' not in acc:
                self.reply(200, f'event: message\ndata: {out}\n\n'.encode(), 'text/event-stream')
            else:
                self.reply(200, out.encode())

        def log_message(self, *a):
            pass

    guard = '토큰 인증' if token else '인증 없음(로컬 전용으로만 써라)'
    print(f'shiliao MCP · http://{host}:{port}/ · {guard}', file=sys.stderr)
    ThreadingHTTPServer((host, port), H).serve_forever()


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--http':
        http(int(a[1]) if len(a) > 1 else 8787, a[2] if len(a) > 2 else '127.0.0.1')
    else:
        stdio()

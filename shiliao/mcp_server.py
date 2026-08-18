#!/usr/bin/env python3
"""사료 인덱스를 MCP 로 연다 — 클로드·코덱스·제미나이(stdio), 챗GPT(HTTP) 공용.

표준 라이브러리만 쓴다. 네 프로바이더가 전부 MCP 를 말하므로 서버 하나면 통합이 하나다.

    python3 -m shiliao.mcp_server              # stdio  (Claude Code / Codex / Gemini CLI)
    python3 -m shiliao.mcp_server --http 8787  # HTTP   (ChatGPT 커넥터 등 원격 클라이언트)
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
}]


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
        if p.get('name') != 'search_sources':
            return {'jsonrpc': '2.0', 'id': rid,
                    'error': {'code': -32602, 'message': f"unknown tool: {p.get('name')}"}}
        r = {'content': [{'type': 'text', 'text': call(p.get('arguments', {}))}]}
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


def http(port):
    """Streamable HTTP 전송. 챗GPT 커넥터처럼 stdio 를 못 붙이는 클라이언트용."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            try:
                res = handle(json.loads(body))
            except Exception as e:                                # noqa: BLE001
                res = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32603, 'message': str(e)}}
            if res is None:
                self.send_response(202); self.end_headers(); return
            out = json.dumps(res, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    print(f'shiliao MCP · http://127.0.0.1:{port}/', file=sys.stderr)
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    a = sys.argv[1:]
    http(int(a[1]) if len(a) > 1 else 8787) if a and a[0] == '--http' else stdio()

"""
LoanSphere — UI preview server
==============================

Ye sirf UI dekhne ke liye hai. Poora backend (torch, database, AI models)
install kiye bina saare pages browser me khul jayenge.

Chalane ka tarika:
    1. Command Prompt kholo
    2. Is project folder me jao
    3. Chalao:  python preview_ui.py
    4. Browser me kholo: http://127.0.0.1:8899

Band karne ke liye Command Prompt me Ctrl+C dabao.

NOTE: Ye asli app nahi hai. Login, file upload, AI — kuch kaam nahi karega,
kyunki backend chal hi nahi raha. Ye sirf dikhne ke liye hai (design check
karne ke liye). Asli app chalane ke liye: python main.py
"""

import base64
import http.server
import json
import os
import socketserver

PORT = 8899
ROOT = os.path.dirname(os.path.abspath(__file__))

# URL -> konsi HTML file dikhani hai (asli Flask routes jaise hi)
ROUTES = {
    '/':                  'index.html',
    '/index':             'index.html',
    '/login':             'login.html',
    '/register':          'register.html',
    '/summarizer':        'summarizer.html',
    '/extractor':         'extractor.html',
    '/chatbot':           'chatbot.html',
    '/generator':         'generator.html',
    '/kyc':               'kyc.html',
    '/financial-profile': 'financial-profile.html',
    '/credit-score':      'credit-score.html',
    '/loan-advisor':      'loan-advisor.html',
}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


# Ek nakli token, taki auth guard hume login page pe wapas na bheje.
_HEADER  = json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode()
_PAYLOAD = json.dumps({'sub': 'demo.user@loansphere.app', 'exp': 4102444800}).encode()
DEMO_TOKEN = _b64(_HEADER) + '.' + _b64(_PAYLOAD) + '.preview'

INJECT = (
    '<script>try{if(!localStorage.getItem("access_token")){'
    f'localStorage.setItem("access_token","{DEMO_TOKEN}");'
    '}}catch(e){}</script>\n</head>'
).encode()


# Nakli API jawab. Kuch pages (financial profile, loan advisor) KYC verify
# na ho toh khulte hi nahi. Preview me backend hai nahi, isliye ye chhote
# demo jawab de dete hain taki saare pages dikh sakein.
FAKE_API = {
    '/api/kyc/status':               {'kyc_status': 'verified'},
    '/api/forms/available-templates': {'available': []},
}


class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # Preview me kuch bhi save/generate nahi hota
        self._send_json(503, {'msg': 'Preview mode: backend band hai. '
                                     'Asli app ke liye python main.py chalao.'})

    def do_GET(self):
        path = self.path.split('?')[0].split('#')[0]

        if path.startswith('/api/'):
            if path in FAKE_API:
                self._send_json(200, FAKE_API[path])
            else:
                # 404 = "abhi koi data nahi" — page apna empty state dikhayega
                self._send_json(404, {'msg': 'Preview mode: koi data nahi.'})
            return

        if path in ROUTES:
            file_path = os.path.join(ROOT, 'frontend', ROUTES[path])
            if not os.path.exists(file_path):
                self.send_error(404, f'Missing: frontend/{ROUTES[path]}')
                return

            with open(file_path, 'rb') as fh:
                body = fh.read().replace(b'</head>', INJECT, 1)

            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return

        # /static/... jaisi baaki files seedha disk se
        super().do_GET()

    def log_message(self, fmt, *args):
        pass  # terminal saaf rakhne ke liye


if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    print('\n  LoanSphere UI preview chal raha hai')
    print(f'  Browser me kholo:  http://127.0.0.1:{PORT}')
    print('  Band karne ke liye Ctrl+C dabao\n')
    try:
        with socketserver.TCPServer(('127.0.0.1', PORT), PreviewHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print('  Preview band ho gaya.\n')
    except OSError as exc:
        print(f'  Server start nahi hua: {exc}')
        print(f'  Shayad port {PORT} pehle se busy hai. File me PORT badal ke dobara chalao.\n')

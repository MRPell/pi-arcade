"""Cabinet simulator: serves sim/index.html and drives CabinetSim over HTTP.

Usage (from the repo root):
    python3 -m sim.server [--port 21000] [--cabinet config/cabinet.dev.json]

GET  /            the simulated cabinet
GET  /api/state   what the cabinet shows
POST /api/input   {"input": "left", "pressed": true}
POST /api/boot    power-cycle: re-reads the cabinet flag and profiles
"""

import argparse
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'src'))

from arcade_profiles.flag import enforce_enabled  # noqa: E402
from arcade_profiles.profiles import load_profiles  # noqa: E402
from sim.cabinet_sim import CabinetSim  # noqa: E402

INPUTS = {'up', 'down', 'left', 'right', '1', '2', '3', '4', '5', '6', 'coin', 'start'}
PAGE = os.path.join(os.path.dirname(__file__), 'index.html')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, body, status=200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(length).decode() or '{}') if length else {}

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            with open(PAGE, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        elif self.path == '/api/state':
            with self.server.lock:
                self._json(self.server.sim.state())
        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        srv = self.server
        if self.path == '/api/input':
            body = self._body()
            if body.get('input') not in INPUTS or not isinstance(body.get('pressed'), bool):
                return self._json({'error': 'input must be one of %s; pressed a bool'
                                   % sorted(INPUTS)}, 400)
            with srv.lock:
                srv.sim.feed(body['input'], body['pressed'])
                self._json(srv.sim.state())
        elif self.path == '/api/boot':
            with srv.lock:
                srv.sim = srv.boot()
                self._json(srv.sim.state())
        else:
            self._json({'error': 'not found'}, 404)


def make_server(port, cabinet_config, profiles_path, state_dir, host='127.0.0.1'):
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.lock = threading.Lock()
    httpd.boot = lambda: CabinetSim(load_profiles(profiles_path),
                                    enforce_enabled(cabinet_config), state_dir)
    httpd.sim = httpd.boot()
    return httpd


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 21000)))
    parser.add_argument('--cabinet', default=os.path.join(REPO, 'config', 'cabinet.dev.json'),
                        help='cabinet flag config (default: the dev one, flag on)')
    parser.add_argument('--profiles', default=os.path.join(REPO, 'config', 'profiles.json'))
    parser.add_argument('--state-dir', default=None,
                        help='where session.json is written (default: a temp dir)')
    args = parser.parse_args()
    state_dir = args.state_dir or tempfile.mkdtemp(prefix='pi-arcade-sim-')
    httpd = make_server(args.port, args.cabinet, args.profiles, state_dir)
    print('Pi Arcade simulator: http://127.0.0.1:%d  (flag %s, state %s)' % (
        args.port, 'on' if httpd.sim.enforce else 'off', state_dir), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()

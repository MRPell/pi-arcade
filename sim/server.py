"""Cabinet simulator: serves sim/index.html and drives CabinetSim over HTTP.

Usage (from the repo root):
    python3 -m sim.server [--port 21000] [--cabinet config/cabinet.dev.json]

GET  /            the simulated cabinet
GET  /api/state   what the cabinet shows
POST /api/input   {"input": "left", "pressed": true}
POST /api/boot    power-cycle: re-reads the cabinet flag and profiles
POST /api/reset-usage  simulator only: forget every play recorded, then power-cycle

The cabinet's settings (the flag and the profiles) live in --state-dir, as on
the Pi. Each start of the simulator writes them fresh from --cabinet and
--profiles and forgets every play; from then on the admin (make admin-sim)
changes them there, and a power-cycle keeps them. The stand-in games' hiscore
saves (hi/) and the high-score holders (scores.json) live there too.
POST /api/clock   simulator only: {"set": "YYYY-MM-DDTHH:MM"} sets the wall
                  clock, {"advance": seconds} lets time pass, {"synced": bool}
                  says whether network time has set the clock
"""

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'src'))

from arcade_profiles import settings  # noqa: E402
from arcade_profiles.flag import enforce_enabled  # noqa: E402
from sim.cabinet_sim import CabinetSim, SimClock  # noqa: E402

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
        elif self.path == '/api/reset-usage':
            with srv.lock:
                try:
                    os.remove(os.path.join(srv.state_dir, 'usage.json'))
                except FileNotFoundError:
                    pass
                srv.sim = srv.boot()
                self._json(srv.sim.state())
        elif self.path == '/api/clock':
            body = self._body()
            with srv.lock:
                try:
                    if 'set' in body:
                        srv.clock.set_wall(dt.datetime.strptime(body['set'], '%Y-%m-%dT%H:%M').timestamp())
                    if 'advance' in body:
                        seconds = float(body['advance'])
                        if seconds < 0:
                            raise ValueError('advance must not be negative')
                        srv.clock.advance(seconds)
                    if 'synced' in body:
                        if not isinstance(body['synced'], bool):
                            raise ValueError('synced must be a bool')
                        srv.clock.synced = body['synced']
                except (TypeError, ValueError) as e:
                    return self._json({'error': str(e)}, 400)
                self._json(srv.sim.state())
        else:
            self._json({'error': 'not found'}, 404)


def fresh_cabinet(state_dir, cabinet_config, profiles_path):
    """The simulated cabinet's disk at the start of a run: the given flag and
    profiles as its settings, no one signed in, no play recorded and no high
    scores."""
    for name in ('usage.json', 'session.json', 'scores.json', 'hi'):
        path = os.path.join(state_dir, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
    with open(profiles_path) as f:
        profiles = json.load(f)
    settings.write({'enforce': enforce_enabled(cabinet_config), 'profiles': profiles}, state_dir)


def make_server(port, cabinet_config, profiles_path, state_dir, host='127.0.0.1', clock=None):
    fresh_cabinet(state_dir, cabinet_config, profiles_path)
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.lock = threading.Lock()
    httpd.clock = clock or SimClock()
    httpd.state_dir = state_dir
    httpd.boot = lambda: CabinetSim(state_dir, httpd.clock)
    httpd.sim = httpd.boot()
    return httpd


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 21000)))
    parser.add_argument('--cabinet', default=os.path.join(REPO, 'config', 'cabinet.dev.json'),
                        help='cabinet flag config (default: the dev one, flag on)')
    parser.add_argument('--profiles', default=os.path.join(REPO, 'config', 'profiles.json'))
    parser.add_argument('--state-dir', default=None,
                        help='the cabinet\'s state and settings, shared with make admin-sim '
                             '(default: a temp dir)')
    args = parser.parse_args()
    state_dir = args.state_dir or tempfile.mkdtemp(prefix='pi-arcade-sim-')
    httpd = make_server(args.port, args.cabinet, args.profiles, state_dir)
    print('Pi Arcade simulator: http://127.0.0.1:%d  (flag %s, state %s)' % (
        args.port, 'on' if httpd.sim.enforce_setting() else 'off', state_dir), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()

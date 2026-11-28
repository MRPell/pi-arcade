"""Arcade profiles admin, run on the owner's computer (make admin).

Changes the cabinet's profiles (names, combos, hours, time limits) and who
holds each high score, and turns arcade-profiles.enforce on and off. It talks to the cabinet over SSH, running
`python3 -m arcade_profiles.settings` there, so only a computer holding the
cabinet's SSH key can change anything, and it listens on 127.0.0.1 only.
`--sim-dir` points it at the simulator's cabinet instead (make admin-sim).

Usage (from the repo root):
    python3 -m admin.server --pi pi@retropie.local [--pi-dir /home/pi/pi-arcade] [--port 21010]
    python3 -m admin.server --sim-dir .sim-cabinet [--port 21010]

GET  /               the admin page
GET  /api/cabinet    {"target", "enforce", "profiles", "from_admin", "scores"} as the cabinet has them
POST /api/profiles   {"profiles": {...}}: checked here, then written to the cabinet
POST /api/enforce    {"enforce": true|false}
POST /api/scores     {"game": "<rom>", "holder": "<profile id>" or null}: who holds that high score
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'src'))

from arcade_profiles.profiles import ProfileError  # noqa: E402
from arcade_profiles.settings import check_profiles  # noqa: E402

PAGE = os.path.join(os.path.dirname(__file__), 'index.html')
TIMEOUT_SECONDS = 20


class CabinetError(Exception):
    """The cabinet could not be reached, or refused the change."""


class Cabinet:
    """The cabinet's settings, reached by running arcade_profiles.settings
    through command (ssh to the Pi, or locally for the simulator)."""

    def __init__(self, command, label, env=None):
        self.command = command
        self.label = label
        self.env = env

    def _run(self, sub, payload=None):
        try:
            proc = subprocess.run(self.command + [sub], env=self.env, timeout=TIMEOUT_SECONDS,
                                  input=None if payload is None else json.dumps(payload).encode(),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise CabinetError('Could not reach the cabinet (%s): %s' % (self.label, e))
        lines = proc.stdout.decode(errors='replace').strip().splitlines()
        try:
            answer = json.loads(lines[-1])
        except (IndexError, ValueError):
            err = proc.stderr.decode(errors='replace').strip().splitlines()
            raise CabinetError('Could not reach the cabinet (%s): %s' % (
                self.label, err[-1] if err else 'no answer (exit %d)' % proc.returncode))
        if 'error' in answer:
            raise CabinetError('The cabinet refused the change: %s' % answer['error'])
        return dict(answer, target=self.label)

    def show(self):
        return self._run('show')

    def write(self, change):
        return self._run('write', change)


def ssh_cabinet(host, pi_dir):
    remote = 'PYTHONPATH=%s python3 -m arcade_profiles.settings' % shlex.quote(pi_dir + '/src')
    return Cabinet(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', host, remote], host)


def sim_cabinet(sim_dir):
    env = dict(os.environ, PYTHONPATH=os.path.join(REPO, 'src'),
               PI_ARCADE_STATE_DIR=os.path.abspath(sim_dir))
    env.pop('PI_ARCADE_CABINET_CONFIG', None)
    return Cabinet([sys.executable, '-m', 'arcade_profiles.settings'],
                   'the simulator (%s)' % os.path.basename(os.path.abspath(sim_dir)), env)


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
        try:
            body = json.loads(self.rfile.read(length).decode() or '{}')
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    def _cabinet(self, call):
        try:
            self._json(call())
        except CabinetError as e:
            self._json({'error': str(e)}, 502)

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
        elif self.path == '/api/cabinet':
            self._cabinet(self.server.cabinet.show)
        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        body = self._body()
        cabinet = self.server.cabinet
        if self.path == '/api/profiles':
            profiles = (body or {}).get('profiles')
            try:
                check_profiles(profiles)
            except ProfileError as e:
                return self._json({'error': str(e)}, 400)
            self._cabinet(lambda: cabinet.write({'profiles': profiles}))
        elif self.path == '/api/enforce':
            enforce = (body or {}).get('enforce')
            if not isinstance(enforce, bool):
                return self._json({'error': 'enforce must be true or false'}, 400)
            self._cabinet(lambda: cabinet.write({'enforce': enforce}))
        elif self.path == '/api/scores':
            body = body or {}
            game, holder = body.get('game'), body.get('holder')
            if not isinstance(game, str) or not (holder is None or isinstance(holder, str)):
                return self._json({'error': 'a score change is {"game": "<game>", '
                                            '"holder": "<profile id>" or null}'}, 400)
            self._cabinet(lambda: cabinet.write({'scores': {game: holder}}))
        else:
            self._json({'error': 'not found'}, 404)


def make_server(port, cabinet):
    # Loopback only: nobody else on the network (or at the cabinet) can reach it.
    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    httpd.cabinet = cabinet
    return httpd


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--pi', help='the cabinet over SSH, e.g. pi@retropie.local')
    target.add_argument('--sim-dir', help="the simulator's cabinet (make sim's state dir)")
    parser.add_argument('--pi-dir', default='/home/pi/pi-arcade')
    parser.add_argument('--port', type=int, default=21010)
    args = parser.parse_args()
    cabinet = ssh_cabinet(args.pi, args.pi_dir) if args.pi else sim_cabinet(args.sim_dir)
    httpd = make_server(args.port, cabinet)
    print('Arcade profiles admin: http://127.0.0.1:%d  (cabinet: %s)' % (args.port, cabinet.label),
          flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()

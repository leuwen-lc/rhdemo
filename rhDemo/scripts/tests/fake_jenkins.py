#!/usr/bin/env python3
"""Faux Jenkins pour le bac à sable du poller (tests/poll-sandbox.sh). Écoute sur 127.0.0.1.

Usage : fake_jenkins.py <dossier> <port>
<dossier>/builds.json, relu à chaque requête :
  {"last": 913, "builds": {"913": {"result": "FAILURE", "wfapi": "913-wfapi.json",
                                   "owasp": "913-owasp.html", "sha": "<sha ou null>"}}}
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = sys.argv[1]


def config():
    with open(os.path.join(ROOT, "builds.json"), encoding="utf-8") as fh:
        return json.load(fh)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, body, ctype="application/json", code=200):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def file(self, name, ctype):
        with open(os.path.join(ROOT, name), "rb") as fh:
            self.send(fh.read(), ctype)

    def do_GET(self):  # noqa: N802 - API http.server
        cfg = config()
        path = self.path.split("?")[0]
        if path == "/job/RHDemo-CI/lastCompletedBuild/api/json":
            last = str(cfg["last"])
            return self.send(json.dumps({"number": cfg["last"], "result": cfg["builds"][last]["result"]}))
        m = re.match(r"^/job/RHDemo-CI/(\d+)/(.*)$", path)
        if not m or m.group(1) not in cfg["builds"]:
            return self.send("{}", code=404)
        build, rest = cfg["builds"][m.group(1)], m.group(2)
        if rest == "wfapi/describe":
            return self.file(build["wfapi"], "application/json")
        if rest == "OWASP_20Dependency-Check_20Report/dependency-check-report.html":
            return self.file(build["owasp"], "text/html")
        if rest == "api/json":
            return self.send(json.dumps({"actions": [{"lastBuiltRevision": {"SHA1": build.get("sha")}}]}))
        if rest == "consoleText":
            return self.send("", "text/plain")
        return self.send("{}", code=404)


HTTPServer(("127.0.0.1", int(sys.argv[2])), Handler).serve_forever()

"""Minimal dependency-light HTTP + SSE server for the five live screens."""
from __future__ import annotations
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from runtime.vx_live_state import LIVE

ROOT=Path(__file__).resolve().parents[1]
SCREEN=ROOT/"screens"
class Handler(BaseHTTPRequestHandler):
    def _send(self,code,body,ctype):
        b=body.encode()
        self.send_response(code); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path=="/api/state":
            self._send(200,json.dumps(LIVE.snapshot(),ensure_ascii=False),"application/json"); return
        if self.path=="/api/events":
            self.send_response(200); self.send_header("Content-Type","text/event-stream"); self.send_header("Cache-Control","no-cache"); self.send_header("Connection","keep-alive"); self.end_headers()
            last=-1
            for _ in range(60):
                snap=LIVE.snapshot()
                if len(snap["events"])!=last:
                    self.wfile.write(("data: "+json.dumps(snap,ensure_ascii=False)+"\n\n").encode()); self.wfile.flush(); last=len(snap["events"])
                time.sleep(1)
            return
        name=self.path.strip("/") or "atomaton_status_monitor.html"
        p=SCREEN/name
        if p.exists() and p.suffix==".html": self._send(200,p.read_text(encoding="utf-8"),"text/html; charset=utf-8"); return
        self._send(404,"not found","text/plain")
    def log_message(self,*args): pass

def serve(host="127.0.0.1",port=8787):
    LIVE.update(status="LIVE")
    LIVE.publish("RUNTIME_STARTED",host=host,port=port)
    ThreadingHTTPServer((host,port),Handler).serve_forever()

if __name__=="__main__":
    serve(host=sys.argv[1] if len(sys.argv)>1 else "127.0.0.1",port=int(sys.argv[2]) if len(sys.argv)>2 else 8787)

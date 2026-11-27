"""Serve the built browser game and its API on loopback for local testing."""

from argparse import ArgumentParser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from api.game import handler


class PreviewHandler(handler, SimpleHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path == "/api/game":
            handler.do_GET(self)
        else:
            SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if urlsplit(self.path).path == "/api/game":
            handler.do_POST(self)
        else:
            self.send_error(404)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    output = Path(__file__).with_name("dist")
    if not (output / "index.html").exists():
        parser.error("Build the browser game first with node scripts/build-web.mjs.")
    with ThreadingHTTPServer(("127.0.0.1", args.port), partial(PreviewHandler, directory=output)) as server:
        print(f"Local http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

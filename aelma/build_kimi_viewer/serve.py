"""AELMA Viewer dev server.

Serves the viewer over HTTP with permissive CORS headers so the page
(and its ES modules) load cleanly from any local origin.

Usage:
    python serve.py [--port 8080]
"""

import argparse
import http.server
import socketserver


class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with Access-Control-Allow-Origin: *."""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="Serve the AELMA viewer with CORS headers.")
    parser.add_argument("--port", type=int, default=8080, help="port to listen on (default: 8080)")
    args = parser.parse_args()

    with socketserver.ThreadingTCPServer(("", args.port), CORSRequestHandler) as httpd:
        httpd.allow_reuse_address = True
        print(f"AELMA viewer at http://localhost:{args.port}/  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

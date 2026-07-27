#!/usr/bin/env python3
"""
AELMA Viewer - Static file server with CORS headers.

Serves the viewer files on a local port for browser testing.
"""

import argparse
import http.server
import os
import socketserver


class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler that adds CORS headers to all responses."""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(
        description="AELMA Viewer static file server with CORS"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to serve on (default: 8080)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Directory to serve from (default: script directory)",
    )
    args = parser.parse_args()

    # Serve from the script's own directory by default
    serve_dir = args.dir or os.path.dirname(os.path.abspath(__file__))
    os.chdir(serve_dir)

    handler = CORSRequestHandler

    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f"AELMA Viewer server running at http://{args.host}:{args.port}")
        print(f"Serving from: {serve_dir}")
        print(f"Open http://localhost:{args.port} in your browser.")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()

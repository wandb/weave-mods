import http.server
import logging
import os
import socketserver
import threading
import time

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEALTHCHECK_PORT = int(os.environ.get("HEALTHCHECK_PORT", 6638))
MAIN_PORT = int(os.environ.get("PORT", 6637))


class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            # Check if main application port is responding
            try:
                # Try to connect to main application port
                requests.get(f"http://localhost:{MAIN_PORT}", timeout=1)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"healthy")
            except requests.RequestException:
                # If main port isn't responding but process might still be starting
                if time.time() - start_time < 30:  # 30 second grace period
                    logger.warning(
                        f"Main application at port {MAIN_PORT} is still starting"
                    )
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"starting")
                else:
                    logger.error(
                        f"Main application at port {MAIN_PORT} is not responding"
                    )
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b"unhealthy")
        else:
            self.send_response(404)
            self.end_headers()


def run_health_server():
    with socketserver.TCPServer(("", HEALTHCHECK_PORT), HealthCheckHandler) as httpd:
        logger.info(f"Serving health check on port {HEALTHCHECK_PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    start_time = time.time()
    threading.Thread(target=run_health_server, daemon=True).start()

    # Keep main thread alive indefinitely
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down health check server")

import http.server
import json
import logging
import os
import signal
import socketserver
import subprocess
import sys
import threading
import time

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEALTHCHECK_PORT = int(os.environ.get("HEALTHCHECK_PORT", 6638))
MAIN_PORT = int(os.environ.get("PORT", 6637))


def create_artifact_snapshot() -> tuple[int, str, str]:
    """
    Create a W&B artifact snapshot by calling artifact-helper.py.

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    logger.info("Creating artifact snapshot")
    try:
        # Call the artifact helper script
        result = subprocess.run(
            ["/app/.venv/bin/python", "/app/src/wandb/artifact-helper.py"],
            capture_output=True,
            text=True,
            timeout=360,  # 6 minute timeout
        )

        return result.returncode, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        error_msg = "Artifact creation timed out after 6 minutes"
        logger.error(error_msg)
        return 1, "", error_msg
    except Exception as e:
        error_msg = f"Unexpected error creating artifact: {e}"
        logger.error(error_msg)
        return 1, "", error_msg


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

    def do_POST(self):
        if self.path == "/snapshot":
            # Create artifact snapshot
            exit_code, stdout, stderr = create_artifact_snapshot()

            if exit_code == 0:
                # Success
                response = {
                    "status": "success",
                    "message": "Artifact snapshot created successfully",
                    "output": stdout,
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            else:
                # Failure
                response = {
                    "status": "error",
                    "message": "Failed to create artifact snapshot",
                    "error": stderr,
                    "output": stdout,
                }
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()


def run_health_server():
    with socketserver.TCPServer(("", HEALTHCHECK_PORT), HealthCheckHandler) as httpd:
        logger.info(f"Serving health check on port {HEALTHCHECK_PORT}")
        httpd.serve_forever()


def shutdown_handler(signum, frame):
    """
    Handle shutdown signals (SIGTERM, SIGINT).
    Creates an artifact snapshot only if WANDB_SNAPSHOT_ON_SHUTDOWN is set to "true".
    """
    signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    logger.info(f"Received {signal_name}")

    # Only create artifact if explicitly enabled
    if os.environ.get("WANDB_SNAPSHOT_ON_SHUTDOWN", "").lower() == "true":
        logger.info("Creating artifact snapshot before shutdown")
        exit_code, stdout, stderr = create_artifact_snapshot()

        if exit_code == 0:
            logger.info("Artifact snapshot created successfully")
        else:
            logger.error(f"Failed to create artifact snapshot: {stderr}")
    else:
        logger.info(
            "Skipping artifact snapshot (set WANDB_SNAPSHOT_ON_SHUTDOWN=true to enable)"
        )

    # Exit gracefully
    logger.info("Shutting down health check server")
    sys.exit(0)


if __name__ == "__main__":
    start_time = time.time()

    # Register signal handlers for graceful shutdown with artifact creation
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    threading.Thread(target=run_health_server, daemon=True).start()

    # Keep main thread alive indefinitely
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        # This shouldn't be reached because SIGINT is handled by shutdown_handler
        logger.info("Shutting down health check server")

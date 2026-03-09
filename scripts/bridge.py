#!/usr/bin/env python3
"""
Trae Bridge - Main Entry Point
REST API server for Trae AI IDE
"""

import sys
import os
import argparse
import logging

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api_server import run_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Trae Bridge - REST API for Trae AI IDE"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind to (default: 8765)"
    )

    parser.add_argument(
        "--cdp-port",
        type=int,
        default=9230,
        help="Trae CDP port (default: 9230)"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)"
    )

    args = parser.parse_args()

    # Set log level
    log_level = getattr(logging, args.log_level)
    logging.getLogger().setLevel(log_level)

    logger.info("Starting Trae Bridge...")
    logger.info(f"API will be available at http://{args.host}:{args.port}")
    logger.info(f"Make sure Trae is running with CDP on port {args.cdp_port}")
    logger.info("")
    logger.info("To start Trae with CDP:")
    logger.info(f"  ./scripts/start_trae.sh")
    logger.info("")
    logger.info("API Endpoints:")
    logger.info("  POST /chat           - Synchronous chat")
    logger.info("  POST /async          - Asynchronous chat")
    logger.info("  GET  /task/{{id}}      - Get async task status")
    logger.info("  POST /new            - Start new chat")
    logger.info("  GET  /health         - Health check")
    logger.info("  GET  /models         - List available models")
    logger.info("  POST /model          - Switch model")
    logger.info("  GET  /history        - Get chat history")
    logger.info("")

    try:
        run_server(host=args.host, port=args.port, cdp_port_param=args.cdp_port)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

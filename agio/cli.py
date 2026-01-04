"""
Command-line interface for Agio.
"""

import argparse
import sys

from agio.api import start_server


def main():
    parser = argparse.ArgumentParser(description="Agio - Modern AI Agent Framework")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8900,
        help="Port to bind to (default: 8900)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )

    args = parser.parse_args()

    kwargs = {}
    if args.workers > 1:
        kwargs["workers"] = args.workers

    try:
        start_server(
            host=args.host,
            port=args.port,
            reload=args.reload,
            **kwargs,
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down Agio server...")
        sys.exit(0)


if __name__ == "__main__":
    main()

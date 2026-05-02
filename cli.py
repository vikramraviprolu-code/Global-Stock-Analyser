"""EquityScope command-line entry point.

Exposed as the `equityscope` console script via pyproject.toml.

Usage:
    equityscope                 # serve on http://127.0.0.1:5050
    equityscope --port 8080
    equityscope --host 0.0.0.0  # bind LAN (NOT recommended; see SECURITY.md)
    equityscope --tls-cert cert.pem --tls-key key.pem
    equityscope --help

Cross-platform: uses Waitress (pure-Python WSGI server) on Windows /
generic Linux, falls back to the Flask dev server only when --debug
is passed. macOS users running the LaunchDaemon installer get
gunicorn instead — see scripts/install_daemon.sh.
"""
from __future__ import annotations

import argparse
import os
import sys


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="equityscope",
        description="Free, no-API-key global equity research dashboard. "
                    "Browser-local single-tenant app.",
    )
    p.add_argument("--host", default="127.0.0.1",
                   help="Bind host (default: 127.0.0.1 — loopback only).")
    p.add_argument("--port", type=int, default=5050,
                   help="Bind port (default: 5050).")
    p.add_argument("--tls-cert", default=os.getenv("SSL_CERT"),
                   help="Path to TLS cert PEM (or env SSL_CERT).")
    p.add_argument("--tls-key", default=os.getenv("SSL_KEY"),
                   help="Path to TLS key PEM (or env SSL_KEY).")
    p.add_argument("--url-prefix", default=os.getenv("URL_PREFIX", ""),
                   help="Mount the app under a URL prefix (default: '').")
    p.add_argument("--debug", action="store_true",
                   help="Run Flask dev server with debugger. NEVER in production.")
    p.add_argument("--no-auto-shutdown", action="store_true",
                   help="Disable browser-driven idle shutdown.")
    p.add_argument("--version", action="store_true",
                   help="Print version and exit.")
    return p


def _print_version() -> None:
    """Resolve and print the version. Falls back to a constant if metadata missing."""
    try:
        from importlib.metadata import version
        print(version("global-stock-analyser"))
    except Exception:
        # Fallback to app.py's pinned value (kept in sync via check_version_sync.sh)
        from app import app  # type: ignore  # noqa: F401
        # Read from /api/settings/server-info code path — same source of truth
        import re
        from pathlib import Path
        body = (Path(__file__).parent / "app.py").read_text()
        m = re.search(r'"version":\s*"([0-9.]+)"', body)
        print(m.group(1) if m else "unknown")


def _serve_waitress(host: str, port: int, tls_cert: str | None,
                    tls_key: str | None) -> None:
    """Production-grade WSGI server — works on Windows, Linux, macOS."""
    if tls_cert and tls_key:
        # Waitress doesn't speak TLS natively — wrap with adhoc Werkzeug
        # SSL context if cert provided. Users wanting hardened TLS should
        # run behind a reverse proxy (nginx / Caddy) or use the macOS
        # LaunchDaemon path.
        print("EquityScope: TLS via --tls-cert is supported only in --debug "
              "mode. For production TLS, run behind a reverse proxy or use "
              "the macOS LaunchDaemon installer.", file=sys.stderr)
        sys.exit(2)

    try:
        from waitress import serve
    except ImportError:
        print("EquityScope: 'waitress' is required to run without --debug. "
              "Install with: pip install 'global-stock-analyser[server]'",
              file=sys.stderr)
        sys.exit(3)

    from app import app
    print(f"EquityScope serving on http://{host}:{port}")
    serve(app, host=host, port=port, threads=8, ident="EquityScope")


def _serve_dev(host: str, port: int, tls_cert: str | None,
               tls_key: str | None) -> None:
    """Flask dev server — debug only."""
    from app import app
    ssl_context = None
    if tls_cert and tls_key:
        ssl_context = (tls_cert, tls_key)
    elif tls_cert or tls_key:
        print("EquityScope: --tls-cert and --tls-key must be provided "
              "together.", file=sys.stderr)
        sys.exit(2)
    app.run(host=host, port=port, ssl_context=ssl_context,
            debug=True, use_reloader=False)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.version:
        _print_version()
        return 0

    if args.url_prefix:
        os.environ["URL_PREFIX"] = args.url_prefix
    if args.no_auto_shutdown:
        os.environ["AUTO_SHUTDOWN"] = "0"

    if args.debug:
        _serve_dev(args.host, args.port, args.tls_cert, args.tls_key)
    else:
        _serve_waitress(args.host, args.port, args.tls_cert, args.tls_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

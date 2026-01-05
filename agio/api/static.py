"""
Static file serving for Agio frontend.

Provides utilities to mount the Agio frontend as static files in FastAPI applications.
"""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles


def get_frontend_dist_path() -> Optional[Path]:
    """
    Get the path to the frontend dist directory.

    Returns:
        Path to frontend dist directory, or None if not found
    """
    package_dir = Path(__file__).parent.parent.parent
    frontend_dist = package_dir / "agio" / "frontend" / "dist"

    if frontend_dist.exists() and frontend_dist.is_dir():
        return frontend_dist

    return None


def mount_frontend(
    app: FastAPI,
    path: str = "/",
    api_prefix: str = "/agio",
) -> bool:
    """
    Mount Agio frontend static files to FastAPI app.

    This will serve the frontend at the specified path, with API routes
    available at the specified prefix.

    Args:
        app: FastAPI application instance
        path: Path prefix to mount frontend (default: "/")
        api_prefix: API prefix used by frontend (default: "/agio")

    Returns:
        True if frontend was mounted successfully, False otherwise

    Example:
        ```python
        from fastapi import FastAPI
        from agio.api import create_router, mount_frontend

        app = FastAPI()

        # Mount API router
        app.include_router(create_router(prefix="/agio"))

        # Mount frontend (serves at root, API at /agio)
        mount_frontend(app, path="/", api_prefix="/agio")
        ```
    """
    frontend_dist = get_frontend_dist_path()

    if frontend_dist is None:
        return False

    # Normalize paths
    frontend_path = path.rstrip("/") or "/"
    api_path = api_prefix.rstrip("/")

    # Mount static assets (JS, CSS, etc.)
    static_dir = frontend_dist / "assets"
    if static_dir.exists():
        assets_path = f"{frontend_path}/assets" if frontend_path != "/" else "/assets"
        app.mount(
            assets_path,
            StaticFiles(directory=str(static_dir)),
            name="agio-frontend-assets",
        )

    # Serve index.html for all routes (SPA support)
    index_html = frontend_dist / "index.html"
    if not index_html.exists():
        return False

    # Create catch-all route for SPA
    # Note: This route should be registered AFTER API routes to avoid conflicts
    async def serve_spa_internal(request: Request):
        """
        Serve index.html for all routes to support SPA routing.
        Excludes API routes to avoid conflicts.
        """
        # Get the request path
        request_path = request.url.path

        # Don't serve frontend for API routes
        if request_path.startswith(api_path):
            return Response(status_code=404)

        # Don't serve frontend for static assets (already handled by mount)
        assets_prefix = f"{frontend_path}/assets" if frontend_path != "/" else "/assets"
        if request_path.startswith(assets_prefix):
            return Response(status_code=404)

        # Serve index.html for all other routes
        return FileResponse(
            str(index_html),
            media_type="text/html",
        )

    # Register catch-all routes
    # These must be registered last (after API routes)
    if frontend_path == "/":
        # Root path: match everything except API
        @app.get("/{full_path:path}", include_in_schema=False)
        async def root_spa(full_path: str, request: Request):
            return await serve_spa_internal(request)
    else:
        # Sub-path: match paths under frontend_path
        @app.get(f"{frontend_path}", include_in_schema=False)
        async def frontend_root(request: Request):
            return await serve_spa_internal(request)

        @app.get(f"{frontend_path}/{{full_path:path}}", include_in_schema=False)
        async def frontend_spa(full_path: str, request: Request):
            return await serve_spa_internal(request)

    return True


def create_app_with_frontend(
    api_prefix: str = "/agio",
    frontend_path: str = "/",
    enable_frontend: bool = True,
) -> FastAPI:
    """
    Create FastAPI app with both API and frontend mounted.

    Args:
        api_prefix: URL prefix for API routes (default: "/agio")
        frontend_path: URL path to mount frontend (default: "/")
        enable_frontend: Whether to mount frontend (default: True)

    Returns:
        Configured FastAPI application

    Example:
        ```python
        from agio.api import create_app_with_frontend

        app = create_app_with_frontend(
            api_prefix="/agio",
            frontend_path="/",
        )
        ```
    """
    from .app import create_app
    from .router import create_router

    app = create_app()

    # Include API router
    app.include_router(create_router(prefix=api_prefix))

    # Mount frontend if enabled
    if enable_frontend:
        mounted = mount_frontend(app, path=frontend_path, api_prefix=api_prefix)
        if not mounted:
            import warnings

            warnings.warn(
                "Agio frontend not found. Frontend will not be served. "
                "Make sure frontend is built and included in the package.",
                UserWarning,
            )

    return app

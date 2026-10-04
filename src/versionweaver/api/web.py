from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles


def mount_web_ui(app: FastAPI, dist_dir: Path) -> None:
    """Serve the compiled React app after API routes, including client-side routing."""
    root = dist_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        return

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def web_app(path: str) -> FileResponse:
        protected_roots = {"api", "health", "metrics", "docs", "redoc", "openapi.json"}
        if path in protected_roots or path.startswith(("api/", "health/")):
            raise HTTPException(status_code=404, detail="not found")
        candidate = (root / path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

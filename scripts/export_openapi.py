"""Script to export the FastAPI OpenAPI schema to docs/openapi.json without running a server.

Usage:
    py -m scripts.export_openapi
or:
    python -m scripts.export_openapi
"""

import json
from pathlib import Path
from fastapi.openapi.utils import get_openapi
from app.main import create_app


def export_openapi_schema(output_path: Path | str = "docs/openapi.json") -> Path:
    """Generate OpenAPI schema dictionary from the FastAPI application and save to disk."""
    app = create_app()
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"Successfully exported OpenAPI schema to {dest.resolve()} ({len(openapi_schema.get('paths', {}))} paths)")
    return dest


if __name__ == "__main__":
    export_openapi_schema()

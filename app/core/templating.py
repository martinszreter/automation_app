"""The one Jinja2 environment every HTML route renders through.

Lives here rather than in ``app.main`` so routers can import it at module
level instead of reaching back into ``app.main`` from inside a request, which
was a circular import waiting to happen.
"""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "html"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def render(request: Request, name: str, status_code: int = 200, **context: Any) -> HTMLResponse:
    """Render ``name`` (a path under templates/html) with ``context``."""
    return templates.TemplateResponse(
        request=request, name=name, context=context, status_code=status_code
    )

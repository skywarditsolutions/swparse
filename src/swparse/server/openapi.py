from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import RapidocRenderPlugin, ScalarRenderPlugin

from swparse.__about__ import __version__ as current_version
from swparse.config import get_settings
from swparse.domain.accounts.guards import auth

settings = get_settings()
config = OpenAPIConfig(
    title=settings.app.NAME,
    version=current_version,
    components=[auth.openapi_components],
    security=[auth.security_requirement],
    use_handler_docstrings=True,
    render_plugins=[
        ScalarRenderPlugin(js_url="/vendor/scalar/api-reference@latest"),
        RapidocRenderPlugin(path="/docs/", js_url="/vendor/rapidocs/rapidoc-min.min.js"),
    ],
)
"""OpenAPI config for swparse.  See OpenAPISettings for configuration."""

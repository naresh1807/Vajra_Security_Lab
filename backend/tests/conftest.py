"""
Ensures every SQLAlchemy-mapped model is imported (and thus registered on
the shared declarative Base) before any test instantiates one. Without
this, `Project.assets = relationship("Asset", ...)` fails to resolve the
string-based "Asset" reference when a test only imports app.projects.models.
"""
import app.auth.models  # noqa: F401
import app.evidence.models  # noqa: F401
import app.diff.models  # noqa: F401
import app.http.models  # noqa: F401
import app.identities.models  # noqa: F401
import app.investigations.models  # noqa: F401
import app.js_inspector.models  # noqa: F401
import app.projects.models  # noqa: F401
import app.recon.models  # noqa: F401
import app.reports.models  # noqa: F401
import app.scopeguard.models  # noqa: F401
import app.surface.models  # noqa: F401

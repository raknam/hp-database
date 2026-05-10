from pathlib import Path
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _vlc_href(nas_path: str) -> str:
    """Generate a vlc://file:/// href that survives browser URL normalization.

    Browsers strip the empty port colon in vlc://T:/path (authority section).
    Wrapping as vlc://file:///T:/path puts T: in the path section (preserved),
    and the vlc-protocol.bat's own `file/=file:/` substitution restores the
    file:// scheme after the browser drops its colon too.
    VLC then receives: --open "file:///T:/path" and URL-decodes %20/%21.
    """
    path = nas_path.replace("\\", "/").replace("!", "%21").replace(" ", "%20")
    return "vlc://file:///" + path


templates.env.filters["vlc_href"] = _vlc_href

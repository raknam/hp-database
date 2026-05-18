from pathlib import Path
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _vlc_href(nas_path: str, disc_type: str | None = None) -> str:
    """Generate a vlc:// href that survives browser URL normalization.

    Browsers strip the empty port colon in vlc://T:/path (authority section).
    Wrapping as vlc://scheme:///T:/path puts T: in the path section (preserved).
    disc_type DVD → dvdsimple:///path#1, BD → bluray:///path#1, else file:///path.
    """
    path = nas_path.replace("\\", "/").replace("!", "%21").replace(" ", "%20")
    dt = (disc_type or "").upper()
    if dt == "DVD":
        return "vlc://dvdsimple:///" + path + "#1"
    if dt in ("BD", "BLU-RAY", "BLURAY"):
        return "vlc://bluray:///" + path + "#1"
    return "vlc://file:///" + path


templates.env.filters["vlc_href"] = _vlc_href

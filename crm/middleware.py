from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponseNotFound, HttpResponseRedirect


class SurfaceMiddleware:
    """Do not expose any administrative routes on the forms host, or vice versa."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        public = request.path.startswith(("/r/", "/public/", "/api/public/"))
        origin = settings.PUBLIC_ORIGIN if public else settings.ADMIN_ORIGIN
        target = urlsplit(origin)
        expected = target.netloc
        host = request.get_host()
        aliases = {
            f"{alias}:{target.port}" if target.port else alias for alias in settings.LOCAL_HOST_ALIASES
        }
        if settings.DEBUG and host in aliases and request.method in {"GET", "HEAD"}:
            # Aliases redirect before session middleware and never serve either surface.
            response = HttpResponseRedirect(origin + request.get_full_path())
            response["Cache-Control"] = "no-store"
            return response
        allowed = {expected}
        if request.path.startswith("/static/"):
            allowed.add(urlsplit(settings.PUBLIC_ORIGIN).netloc)
        if host not in allowed:
            return HttpResponseNotFound("Not found")
        response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if public:
            response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

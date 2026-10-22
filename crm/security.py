from django.http import JsonResponse


def no_client_ip(request):
    """Account lockouts do not require storing or trusting client IP addresses."""
    return None


def login_locked_out(request, credentials=None, *args, **kwargs):
    response = JsonResponse(
        {"detail": "Too many failed sign-in attempts. Please try again in 10 minutes."},
        status=429,
    )
    response["Retry-After"] = "600"
    response["Cache-Control"] = "no-store"
    return response

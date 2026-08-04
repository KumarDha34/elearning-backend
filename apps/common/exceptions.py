from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default exception handler so every error response has a
    consistent shape: {"detail": <message or dict>, "code": <exception class>}.
    Keeps client-side error handling (React/Flutter) simple and uniform
    across every endpoint in the API.
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        response.data = {
            "detail": response.data,
            "code": exc.__class__.__name__,
        }

    return response

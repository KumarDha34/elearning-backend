# apps/accounts/schema.py

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SignupTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    Tells drf-spectacular how to represent SignupTokenAuthentication in the
    OpenAPI schema. It reuses the same Bearer scheme as JWTAuthentication,
    so Swagger UI shows one Authorize field for both token types.
    """
    target_class = 'apps.accounts.authentication.SignupTokenAuthentication'
    name = 'jwtAuth'   

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
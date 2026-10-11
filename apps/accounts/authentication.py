from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model

from .tokens import SignupToken


class SignupTokenAuthentication(BaseAuthentication):
    """
    Authenticates requests using a SignupToken (scope='signup:complete').
    Rejects anything else, including regular access tokens.
    """

    keyword = 'Bearer'

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith(self.keyword + ' '):
            return None   # no auth attempted — let other classes try

        raw_token = auth_header[len(self.keyword) + 1:].strip()
        if not raw_token:
            return None

        try:
            validated = SignupToken(raw_token)
        except TokenError as e:
            raise AuthenticationFailed({
                'detail': 'Invalid or expired signup token.',
                'code': 'token_not_valid',
            })

        if validated.get('scope') != 'signup:complete':
            raise AuthenticationFailed({
                'detail': 'Token scope does not allow this operation.',
                'code': 'invalid_scope',
            })

        User = get_user_model()
        try:
            user = User.objects.get(id=validated['user_id'])
        except User.DoesNotExist:
            raise AuthenticationFailed({
                'detail': 'User no longer exists.',
                'code': 'user_not_found',
            })

        if not user.is_active:
            raise AuthenticationFailed({
                'detail': 'User account is inactive.',
                'code': 'user_inactive',
            })

        return (user, validated)
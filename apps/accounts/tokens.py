from datetime import timedelta
from rest_framework_simplejwt.tokens import Token


class SignupToken(Token):
    """
    Short-lived, scope-restricted token issued after OTP verification.
    It only grants access to the profile-completion endpoint.
    """
    token_type = 'signup'
    lifetime = timedelta(minutes=30)


def create_signup_token(user):
    token = SignupToken()
    token['user_id'] = user.id
    token['phone_number'] = user.phone_number
    token['scope'] = 'signup:complete'
    return str(token)
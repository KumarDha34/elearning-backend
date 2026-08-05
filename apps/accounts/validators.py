import re
from django.core.exceptions import ValidationError


def validate_nepali_phone_number(value):
    """Validate Nepali phone numbers: 10 digits starting with 96, 97, or 98"""
    pattern = r'^9[678]\d{8}$'
    if not re.match(pattern, str(value)):
        raise ValidationError(
            'Enter a valid Nepali mobile number (10 digits starting with 96, 97, or 98)'
        )
    return value
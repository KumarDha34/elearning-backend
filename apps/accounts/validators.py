import re
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

import os
PHONE_PATTERN = r'^9[678]\d{8}$'

def validate_nepali_phone_number(value, serializer_mode=False):
    """
    Validate Nepali phone numbers: 10 digits starting with 96, 97, or 98
    
    Args:
        value: Phone number to validate
        serializer_mode: If True, returns serializer-friendly message
    """
    value_str = str(value)
    
    if not re.match(PHONE_PATTERN, value_str):
        if serializer_mode:
            raise ValidationError(
                'Invalid phone number format. Must be a valid Nepali phone number (e.g., 9841234567).'
            )
        raise ValidationError(
            'Enter a valid Nepali mobile number (10 digits starting with 96, 97, or 98)'
        )
    return value

def validate_image_file(value):
    """
    Validate image files: Only PNG, JPG, JPEG allowed
    """
    # Allowed extensions
    allowed_extensions = ['png', 'jpg', 'jpeg']
    
    # Get file extension
    ext = os.path.splitext(value.name)[1].lower().replace('.', '')
    
    if ext not in allowed_extensions:
        raise ValidationError(
            f'Invalid file format. Only {", ".join(allowed_extensions).upper()} files are allowed.'
        )
    
    # Check file size (optional - 5MB max)
    if value.size > 5 * 1024 * 1024:  # 5MB
        raise ValidationError('File size exceeds 5MB limit.')
    
    return value


def validate_verification_document(value):
    """
    Validate verification documents: Only PDF allowed
    """
    # Allowed extensions
    allowed_extensions = ['pdf']
    
    # Get file extension
    ext = os.path.splitext(value.name)[1].lower().replace('.', '')
    
    if ext not in allowed_extensions:
        raise ValidationError(
            f'Invalid file format. Only {", ".join(allowed_extensions).upper()} files are allowed.'
        )
    
    # Check file size (optional - 10MB max)
    if value.size > 10 * 1024 * 1024:  # 10MB
        raise ValidationError('File size exceeds 10MB limit.')
    
    return value
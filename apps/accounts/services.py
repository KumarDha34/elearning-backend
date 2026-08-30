import secrets
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from .models import OTPVerification
import os
logger = logging.getLogger(__name__)


class OTPService:
    """OTP Service with console logging for development"""

    def __init__(self):
        self.expiry_minutes = settings.OTP_EXPIRY_MINUTES
        self.max_attempts = settings.OTP_MAX_ATTEMPTS
        self.code_length = settings.OTP_LENGTH

    @transaction.atomic
    def generate_otp(self, phone_number: str, purpose: str) -> OTPVerification:
        """Generate and store OTP"""
        # Clean up old unverified OTPs
        OTPVerification.objects.filter(
            phone_number=phone_number,
            purpose=purpose,
            is_verified=False,
            is_used=False
        ).update(is_used=True)

        # Generate random OTP
        code = ''.join([str(secrets.randbelow(10)) for _ in range(self.code_length)])
        now = timezone.now()
        # Create OTP record
        otp = OTPVerification(
            phone_number=phone_number,
            otp_code=code,
            purpose=purpose,
            max_attempts=self.max_attempts,
            created_at=now,  # ✅ Explicitly set
            expires_at=now + timezone.timedelta(minutes=self.expiry_minutes)  # ✅ Set expiry
        )
        otp.save()

        # Log OTP to console
        self._log_otp(phone_number, code, purpose)

        return otp

    def verify_otp(self, phone_number: str, purpose: str, code: str) -> bool:
        """Verify OTP"""
        try:
            otp = OTPVerification.objects.filter(
                phone_number=phone_number,
                purpose=purpose,
                is_verified=False,
                is_used=False
            ).latest('created_at')
        except OTPVerification.DoesNotExist:
            raise ValueError("No valid OTP found. Please request a new one.")

        if not otp.is_valid():
            if otp.is_expired():
                raise ValueError("OTP has expired. Please request a new one.")
            if otp.is_exhausted():
                raise ValueError("Maximum attempts exceeded. Please request a new OTP.")
            raise ValueError("Invalid OTP.")

        if otp.otp_code != code:
            otp.increment_attempts()
            remaining = otp.max_attempts - otp.attempt_count
            raise ValueError(f"Invalid code. {remaining} attempts remaining.")

        otp.mark_verified()
        logger.info(f"OTP verified for {phone_number} ({purpose})")
        return True

    def _log_otp(self, phone_number: str, code: str, purpose: str):
        """Log OTP to console"""
        if os.environ.get('DJANGO_DEBUG','False') == 'True':
            print("\n" + "=" * 60)
            print("📱 OTP VERIFICATION")
            print("=" * 60)
            print(f"📞 Phone: {phone_number}")
            print(f"🔑 Code: {code}")
            print(f"📝 Purpose: {purpose}")
            print(f"⏰ Expires in: {self.expiry_minutes} minutes")
            print("=" * 60)
            print("⚠️  For development only. In production, this will be sent via SMS.\n")

        logger.info(f"OTP generated for {phone_number[-4:]} ({purpose})")


# Singleton instance
otp_service = OTPService()
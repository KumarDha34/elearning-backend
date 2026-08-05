import random
from django.utils import timezone
from .models import OTPVerification


class OTPService:
    
    @staticmethod
    def generate_otp():
        return f"{random.randint(100000, 999999)}"
    
    @staticmethod
    def send_otp(phone, purpose='signup'):
        otp = OTPService.generate_otp()
        
        OTPVerification.objects.create(
            phone=phone,
            otp=otp,
            purpose=purpose,
            created_at=timezone.now()
        )
        
        print(f"\n{'='*50}")
        print(f"OTP for {phone}")
        print(f"Code: {otp}")
        print(f"Purpose: {purpose}")
        print(f"{'='*50}\n")
        
        return otp
    
    @staticmethod
    def verify_otp(phone, otp, purpose='signup'):
        try:
            otp_record = OTPVerification.objects.filter(
                phone=phone, verified=False, purpose=purpose
            ).latest('created_at')
            
            if otp_record.is_expired():
                return {'success': False, 'message': 'OTP expired'}
            if not otp_record.can_retry():
                return {'success': False, 'message': 'Too many attempts'}
            if otp_record.otp != otp:
                otp_record.increment_attempts()
                return {'success': False, 'message': f'Invalid OTP. {5 - otp_record.attempts} attempts remaining'}
            
            otp_record.verified = True
            otp_record.save(update_fields=['verified'])
            return {'success': True, 'message': 'OTP verified'}
            
        except OTPVerification.DoesNotExist:
            return {'success': False, 'message': 'No pending OTP found'}
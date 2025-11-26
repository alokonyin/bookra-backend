"""
SMS utility functions using Twilio
"""
import os
import random
from twilio.rest import Client
from datetime import datetime, timedelta, timezone

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Initialize Twilio client
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None
except Exception as e:
    print(f"Warning: Failed to initialize Twilio client: {e}")
    twilio_client = None


def generate_otp() -> str:
    """Generate a 6-digit OTP code"""
    return str(random.randint(100000, 999999))


def send_otp_sms(phone: str, otp_code: str, purpose: str = "verification") -> bool:
    """
    Send OTP code via SMS using Twilio

    Args:
        phone: Phone number in E.164 format (e.g., +254712345678)
        otp_code: The 6-digit OTP code
        purpose: Purpose of OTP (signup, signin, password_reset)

    Returns:
        bool: True if SMS sent successfully, False otherwise
    """
    if not twilio_client:
        print("⚠️ Twilio not configured. OTP code:", otp_code)
        # In development, print OTP to console
        print(f"📱 [DEV MODE] OTP for {phone}: {otp_code}")
        return True  # Return True in dev mode for testing

    try:
        # Format message based on purpose
        if purpose == "signup":
            message_body = f"Welcome to Bookra! Your verification code is: {otp_code}. Valid for 10 minutes."
        elif purpose == "signin":
            message_body = f"Your Bookra login code is: {otp_code}. Valid for 10 minutes."
        elif purpose == "password_reset":
            message_body = f"Your Bookra password reset code is: {otp_code}. Valid for 10 minutes."
        else:
            message_body = f"Your Bookra verification code is: {otp_code}. Valid for 10 minutes."

        # Send SMS via Twilio
        message = twilio_client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=phone
        )

        print(f"✅ SMS sent successfully. SID: {message.sid}")
        return True

    except Exception as e:
        print(f"❌ Failed to send SMS: {e}")
        # In development, still print OTP for testing
        if os.getenv("ENV") != "production":
            print(f"📱 [DEV MODE] OTP for {phone}: {otp_code}")
        return False


def format_phone_number(phone: str) -> str:
    """
    Format phone number to E.164 format

    Examples:
        +254712345678 -> +254712345678 (already formatted)
        0712345678 -> +254712345678 (Kenya)
        712345678 -> +254712345678 (Kenya)
        +211912345678 -> +211912345678 (South Sudan)
    """
    # Remove spaces and dashes
    phone = phone.replace(" ", "").replace("-", "")

    # Already in E.164 format
    if phone.startswith("+"):
        return phone

    # Kenya numbers starting with 0
    if phone.startswith("0"):
        return f"+254{phone[1:]}"

    # Kenya numbers without leading 0
    if len(phone) == 9 and phone[0] in ["7", "1"]:
        return f"+254{phone}"

    # Default: assume it needs +254 (Kenya)
    # TODO: Add more country code logic based on user selection
    return f"+254{phone}" if not phone.startswith("+") else phone


def get_otp_expiry() -> datetime:
    """Get OTP expiry time (10 minutes from now)"""
    return datetime.now(timezone.utc) + timedelta(minutes=10)


def is_otp_expired(expires_at: datetime) -> bool:
    """Check if OTP has expired"""
    return datetime.now(timezone.utc) > expires_at

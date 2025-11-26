"""
OTP (One-Time Password) authentication endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from ..database import get_db
from ..models import OTPVerification, User
from ..utils.sms_utils import generate_otp, send_otp_sms, format_phone_number, get_otp_expiry, is_otp_expired

router = APIRouter(prefix="/auth/otp", tags=["OTP"])


# -------------------------
# Schemas
# -------------------------
class SendOTPRequest(BaseModel):
    phone: str
    purpose: str  # 'signup', 'signin', 'password_reset'


class VerifyOTPRequest(BaseModel):
    phone: str
    otp_code: str
    purpose: str


class OTPResponse(BaseModel):
    success: bool
    message: str
    phone: str


# -------------------------
# Send OTP endpoint
# -------------------------
@router.post("/send", response_model=OTPResponse)
def send_otp(payload: SendOTPRequest, db: Session = Depends(get_db)):
    """
    Send OTP code to phone number

    Purpose types:
    - 'signup': New user registration
    - 'signin': Existing user login
    - 'password_reset': Reset forgotten password
    """
    # Format phone number to E.164
    formatted_phone = format_phone_number(payload.phone)

    # Validate purpose
    valid_purposes = ["signup", "signin", "password_reset"]
    if payload.purpose not in valid_purposes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid purpose. Must be one of: {', '.join(valid_purposes)}"
        )

    # For signup: Check if phone already exists
    if payload.purpose == "signup":
        existing_user = db.query(User).filter(User.phone == formatted_phone).first()
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Phone number already registered. Please sign in instead."
            )

    # For signin/password_reset: Check if phone exists
    if payload.purpose in ["signin", "password_reset"]:
        user = db.query(User).filter(User.phone == formatted_phone).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Phone number not registered. Please sign up first."
            )

    # Invalidate any previous unverified OTPs for this phone + purpose
    db.query(OTPVerification).filter(
        OTPVerification.phone == formatted_phone,
        OTPVerification.purpose == payload.purpose,
        OTPVerification.is_verified == False
    ).update({"is_verified": True})  # Mark as used
    db.commit()

    # Generate new OTP
    otp_code = generate_otp()
    expires_at = get_otp_expiry()

    # Save OTP to database
    otp_record = OTPVerification(
        phone=formatted_phone,
        otp_code=otp_code,
        purpose=payload.purpose,
        expires_at=expires_at,
        is_verified=False
    )
    db.add(otp_record)
    db.commit()

    # Send SMS
    sms_sent = send_otp_sms(formatted_phone, otp_code, payload.purpose)

    if not sms_sent:
        raise HTTPException(
            status_code=500,
            detail="Failed to send SMS. Please try again."
        )

    return OTPResponse(
        success=True,
        message=f"OTP sent to {formatted_phone}. Valid for 10 minutes.",
        phone=formatted_phone
    )


# -------------------------
# Verify OTP endpoint
# -------------------------
@router.post("/verify", response_model=OTPResponse)
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    """
    Verify OTP code entered by user
    """
    # Format phone number
    formatted_phone = format_phone_number(payload.phone)

    # Find the most recent OTP for this phone + purpose
    otp_record = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.phone == formatted_phone,
            OTPVerification.purpose == payload.purpose,
            OTPVerification.is_verified == False
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=404,
            detail="No pending OTP found. Please request a new code."
        )

    # Check if OTP expired
    if is_otp_expired(otp_record.expires_at):
        raise HTTPException(
            status_code=400,
            detail="OTP has expired. Please request a new code."
        )

    # Verify OTP code
    if otp_record.otp_code != payload.otp_code:
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP code. Please try again."
        )

    # Mark OTP as verified
    otp_record.is_verified = True
    otp_record.verified_at = datetime.now(timezone.utc)
    db.commit()

    return OTPResponse(
        success=True,
        message="OTP verified successfully",
        phone=formatted_phone
    )


# -------------------------
# Resend OTP endpoint
# -------------------------
@router.post("/resend", response_model=OTPResponse)
def resend_otp(payload: SendOTPRequest, db: Session = Depends(get_db)):
    """
    Resend OTP code (same as send, but with rate limiting logic)
    """
    formatted_phone = format_phone_number(payload.phone)

    # Check for recent OTP requests (rate limiting)
    recent_otp = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.phone == formatted_phone,
            OTPVerification.purpose == payload.purpose
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if recent_otp:
        # Check if last OTP was sent less than 1 minute ago
        time_since_last = datetime.now(timezone.utc) - recent_otp.created_at
        if time_since_last.total_seconds() < 60:
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {60 - int(time_since_last.total_seconds())} seconds before requesting a new code."
            )

    # Reuse the send_otp logic
    return send_otp(payload, db)

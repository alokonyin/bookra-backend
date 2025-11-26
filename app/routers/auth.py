from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
from ..database import get_db
from ..models import User, RoleEnum, OperatorApplication
from ..schemas import SignupIn, LoginIn, TokenOut, UserOut
from ..security import hash_password, verify_password, make_token
from app.core.config import settings
import os

router = APIRouter(prefix="/auth", tags=["auth"])

# -------------------------
# 🔒 Auth setup
# -------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# -------------------------
# 🧩 Helper: current user
# -------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise credentials_exception

    return user


# -------------------------
# 🧍 Signup endpoint
# -------------------------
@router.post("/signup", response_model=UserOut, status_code=201)
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    # Validate role
    try:
        role = RoleEnum(payload.role)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid role")

    # 👤 TRAVELER SIGNUP: Phone is required (OTP verified)
    if role == RoleEnum.traveler:
        if not payload.phone:
            raise HTTPException(
                status_code=400,
                detail="Phone number is required for traveler signup"
            )

        # Check if phone already exists
        if db.query(User).filter(User.phone == payload.phone).first():
            raise HTTPException(status_code=409, detail="Phone number already registered")

        # Note: OTP verification should happen before this endpoint
        # Frontend should call /auth/otp/verify first, then call this endpoint

        # Create traveler user
        user = User(
            phone=payload.phone,
            email=payload.email,  # Optional
            password_hash=hash_password(payload.password),
            role=role,
            name=payload.name,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return UserOut(
            id=user.id,
            role=user.role.value,
            email=user.email,
            phone=user.phone,
        )

    # 🏢 OPERATOR SIGNUP: Now simplified - no domain verification
    # Operators submit an application for admin approval
    if role == RoleEnum.operator:
        raise HTTPException(
            status_code=400,
            detail="Operator signup has moved to /auth/operator/apply. Please submit an application for admin approval."
        )

    # 👥 OFFICE SIGNUP: Still uses invite tokens (handled separately)
    if role == RoleEnum.office:
        raise HTTPException(
            status_code=400,
            detail="Office users must sign up via invite link. Contact your operator."
        )

    # ⚠️ Default fallback for other roles
    if not (payload.email or payload.phone):
        raise HTTPException(status_code=400, detail="Provide email or phone")

    # Ensure unique email/phone
    if payload.email and db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if payload.phone and db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(status_code=409, detail="Phone already registered")

    # ✅ Create user record for other roles (e.g., admin)
    user = User(
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=role,
        name=payload.name,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return UserOut(
        id=user.id,
        role=user.role.value,
        email=user.email,
        phone=user.phone,
    )



# -------------------------
# 🔑 Login endpoint
# -------------------------
@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    ident = payload.identifier.strip()

    user = db.query(User).filter(
        or_(User.email == ident, User.phone == ident)
    ).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Create JWT token
    token = make_token({"sub": str(user.id), "role": user.role.value})

    return TokenOut(
        access_token=token,
        user={
            "id": user.id,
            "role": user.role.value,
            "email": user.email,
            "phone": user.phone,
            "office_id": user.office_id,
        },
    )

# -------------------------
# 🧑‍💼 Admin Bootstrap (Dev Only) (will delete after)
# -------------------------

@router.post("/admin/bootstrap")
def bootstrap_admin(db: Session = Depends(get_db)):
    # ✅ Disable in production for security
    if os.getenv("ENV") == "production":
        raise HTTPException(status_code=403, detail="This endpoint is disabled in production")

    # Check if admin exists
    existing = db.query(User).filter(User.role == RoleEnum.admin).first()
    if existing:
        return {"detail": "Admin already exists"}

    # Create default admin
    admin = User(
        email="admin@bookra.com",
        password_hash=hash_password("admin123"),
        role=RoleEnum.admin,
        name="Bookra Admin",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    return {
        "id": admin.id,
        "role": admin.role.value,
        "email": admin.email,
    }


# -------------------------
# 🏢 Operator Application (New Signup Flow)
# -------------------------
class OperatorApplicationRequest(BaseModel):
    company_name: str
    contact_name: str
    contact_phone: str
    contact_email: Optional[EmailStr] = None
    business_registration_number: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None


@router.post("/operator/apply")
def apply_as_operator(payload: OperatorApplicationRequest, db: Session = Depends(get_db)):
    """
    Submit an operator application for admin review.
    No domain verification required - manual admin approval.
    """
    # Check if phone already has a pending application
    existing_application = (
        db.query(OperatorApplication)
        .filter(
            OperatorApplication.contact_phone == payload.contact_phone,
            OperatorApplication.status == "pending"
        )
        .first()
    )

    if existing_application:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending application. Please wait for admin review."
        )

    # Check if phone already registered as operator
    existing_user = (
        db.query(User)
        .filter(
            User.phone == payload.contact_phone,
            User.role == RoleEnum.operator
        )
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="This phone number is already registered as an operator."
        )

    # Create new application
    application = OperatorApplication(
        company_name=payload.company_name,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        contact_email=payload.contact_email,
        business_registration_number=payload.business_registration_number,
        country=payload.country,
        city=payload.city,
        address=payload.address,
        description=payload.description,
        status="pending"
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    return {
        "success": True,
        "message": "Application submitted successfully. Our team will review your application within 1-2 business days.",
        "application_id": application.id,
        "status": application.status
    }


# -------------------------
# 🔓 Operator Account Setup (After Admin Approval)
# -------------------------
class OperatorSetupRequest(BaseModel):
    phone: str
    otp_code: str
    password: str


@router.post("/operator/complete-setup")
def complete_operator_setup(payload: OperatorSetupRequest, db: Session = Depends(get_db)):
    """
    Complete operator account setup after admin approval.
    Operator receives OTP via SMS and uses it to set their password.
    """
    from app.utils.sms_utils import format_phone_number
    from app.models import OTPVerification
    from datetime import datetime, timezone

    formatted_phone = format_phone_number(payload.phone)

    # 1. Verify OTP with purpose "operator_setup"
    otp_record = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.phone == formatted_phone,
            OTPVerification.purpose == "operator_setup",
            OTPVerification.is_verified == False
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=404,
            detail="No pending OTP found. Please request a new OTP from admin."
        )

    # Check if OTP expired
    if otp_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="OTP has expired. Please request a new OTP from admin."
        )

    # Verify OTP code
    if otp_record.otp_code != payload.otp_code:
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP code. Please try again."
        )

    # 2. Find the approved application
    application = (
        db.query(OperatorApplication)
        .filter(
            OperatorApplication.contact_phone == formatted_phone,
            OperatorApplication.status == "approved"
        )
        .first()
    )

    if not application:
        raise HTTPException(
            status_code=404,
            detail="No approved application found for this phone number."
        )

    # 3. Check if operator user already exists
    existing_user = (
        db.query(User)
        .filter(User.phone == formatted_phone)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this phone number already exists."
        )

    # 4. Create operator user account
    operator = User(
        phone=formatted_phone,
        email=application.contact_email,
        password_hash=hash_password(payload.password),
        role=RoleEnum.operator,
        name=application.contact_name,
        company_name=application.company_name,
    )

    db.add(operator)

    # 5. Mark OTP as verified
    otp_record.is_verified = True
    otp_record.verified_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(operator)

    return {
        "success": True,
        "message": f"Operator account created successfully! You can now log in.",
        "operator_id": operator.id,
        "phone": operator.phone,
        "company_name": operator.company_name
    }

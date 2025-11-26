from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.models import Booking, Trip, User

from app.database import get_db
from app.models import (
    User,
    PaymentMethod,
    Payment,
    RoleEnum,
    VerifiedOperator,
    OperatorApplication,
)
from app.schemas import (
    PaymentMethodCreate,
    PaymentMethodOut,
    VerifiedOperatorCreate,
    VerifiedOperatorOut,
)
from app.routers.auth import get_current_user


router = APIRouter(prefix="/v1/admin", tags=["Admin"])

# ----------------------------
# 🧮 1️⃣ Admin Dashboard Summary
# ----------------------------
@router.get("/dashboard")
def admin_dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    total_operators = db.query(User).filter(User.role == RoleEnum.operator).count()
    total_revenue = db.query(func.sum(Payment.amount)).scalar() or 0.0

    return {
        "total_revenue": total_revenue,
        "total_operators": total_operators,
    }


# ----------------------------
# 💳 2️⃣ Admin Payment Method Management
# ----------------------------
@router.post("/payment-method", response_model=PaymentMethodOut)
def set_admin_payment(
    payload: PaymentMethodCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    existing = db.query(PaymentMethod).filter(PaymentMethod.operator_id == None).first()

    if existing:
        existing.account_name = payload.account_name
        existing.account_number = payload.account_number
        existing.bank_name = payload.bank_name
    else:
        existing = PaymentMethod(
            operator_id=None,
            account_name=payload.account_name,
            account_number=payload.account_number,
            bank_name=payload.bank_name,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


@router.get("/payment-method", response_model=PaymentMethodOut)
def get_admin_payment(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    pm = db.query(PaymentMethod).filter(PaymentMethod.operator_id == None).first()
    if not pm:
        raise HTTPException(status_code=404, detail="Payment method not set")

    return pm


# ----------------------------
# 🏢 3️⃣ Verified Operator Management
# ----------------------------

# ----------------------------
# 🏢 3️⃣ Verified Operator Management
# ----------------------------

from pydantic import BaseModel
from typing import Optional, List

# ✅ Create a verified operator
@router.post("/operators", response_model=VerifiedOperatorOut)
def add_verified_operator(
    payload: VerifiedOperatorCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # ✅ Ensure only admins can perform this action
    if user.role != RoleEnum.admin and getattr(user.role, "value", None) != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    # ✅ Check for duplicates (by company_name, contact_email, contact_phone, or company_domain)
    existing = (
        db.query(VerifiedOperator)
        .filter(
            or_(
                VerifiedOperator.company_name.ilike(payload.company_name),
                VerifiedOperator.contact_email == payload.contact_email,
                VerifiedOperator.contact_phone == payload.contact_phone,
                VerifiedOperator.company_domain == payload.company_domain,  # ✅ added domain check
            )
        )
        .first()
    )

    if existing:
        return {
            "id": existing.id,
            "company_name": existing.company_name,
            "company_domain": existing.company_domain,
            "contact_name": existing.contact_name,
            "contact_email": existing.contact_email,
            "contact_phone": existing.contact_phone,
            "verified_by_admin": existing.verified_by_admin,
            "detail": f"Operator '{existing.company_name}' already exists (duplicate company/email/phone/domain). Returning existing record.",
        }

    # ✅ Create a new verified operator
    operator = VerifiedOperator(**payload.dict(exclude_unset=True))
    db.add(operator)
    db.commit()
    db.refresh(operator)
    return operator


# ✅ List all verified operators
@router.get("/operators", response_model=List[VerifiedOperatorOut])
def list_verified_operators(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    return db.query(VerifiedOperator).order_by(VerifiedOperator.created_at.desc()).all()


# ✅ Update verified operator info
class VerifiedOperatorUpdate(BaseModel):
    company_name: Optional[str] = None
    company_domain: Optional[str] = None  # ✅ include domain in updates
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


@router.patch("/operators/{operator_id}", response_model=VerifiedOperatorOut)
def update_verified_operator(
    operator_id: int,
    payload: VerifiedOperatorUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Unauthorized")

    op = db.query(VerifiedOperator).filter(VerifiedOperator.id == operator_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(op, field, value)

    db.commit()
    db.refresh(op)
    return op


# ❌ Delete a verified operator
@router.delete("/operators/{operator_id}")
def delete_verified_operator(
    operator_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Unauthorized")

    op = db.query(VerifiedOperator).filter(VerifiedOperator.id == operator_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")

    db.delete(op)
    db.commit()
    return {"message": f"Operator '{op.company_name}' deleted successfully."}


@router.get("/metrics")
def admin_metrics(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if getattr(user.role, "value", str(user.role)) != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    # counts
    total_operators = db.query(User).filter(User.role == RoleEnum.operator).count()
    total_travelers = db.query(User).filter(User.role == RoleEnum.traveler).count()

    total_bookings = db.query(func.count(Booking.id)).scalar() or 0

    # payments (sum all successful payments)
    # Note: payments table structure is: id, booking_id, method, status, amount, transaction_id, timestamp
    sums_sql = text("""
        SELECT
          COALESCE(SUM(CASE WHEN status='success' THEN amount * 0.05 END), 0) AS platform_revenue,
          COALESCE(SUM(CASE WHEN status='success' THEN amount * 0.95 END), 0) AS operator_revenue,
          COALESCE(SUM(CASE WHEN status='success' THEN amount END), 0) AS total_flow
        FROM payments
    """)
    row = db.execute(sums_sql).mappings().first() or {}
    return {
        "total_operators": total_operators,
        "total_travelers": total_travelers,
        "total_bookings": total_bookings,
        "platform_revenue": float(row.get("platform_revenue", 0)),
        "operator_revenue": float(row.get("operator_revenue", 0)),
        "total_payment_flow": float(row.get("total_flow", 0)),
    }


@router.get("/recent-payments")
def admin_recent_payments(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if getattr(user.role, "value", str(user.role)) != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    # Payments table structure: id, booking_id, method, status, amount, transaction_id, timestamp
    # Bookings table structure: passengers (not num_seats), total_amount (not total_price)
    sql = text("""
        SELECT
          p.id, p.booking_id, p.method, p.status, p.amount,
          p.transaction_id, p.timestamp,
          b.passengers, b.total_amount,
          u.email AS traveler_email, u.phone AS traveler_phone
        FROM payments p
        LEFT JOIN bookings b ON b.id = p.booking_id
        LEFT JOIN users u ON u.id = b.traveler_id
        ORDER BY p.timestamp DESC
        LIMIT 10
    """)
    rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]


@router.get("/recent-bookings")
def admin_recent_bookings(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if getattr(user.role, "value", str(user.role)) != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    sql = text("""
        SELECT
          b.id AS booking_id,
          b.traveler_id,
          b.trip_id,
          b.passengers,
          b.total_amount,
          b.status,
          b.created_at,
          b.contact_email,
          b.contact_phone,
          t.from_city,
          t.to_city,
          t.date,
          t.time,
          u.email AS traveler_email
        FROM bookings b
        LEFT JOIN trips t ON t.id = b.trip_id
        LEFT JOIN users u ON u.id = b.traveler_id
        ORDER BY b.created_at DESC
        LIMIT 10;
    """)

    rows = db.execute(sql).mappings().all()
    return [dict(r) for r in rows]

# ----------------------------
# 🏢 Operator Application Management
# ----------------------------
@router.get("/operator-applications")
def list_operator_applications(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    List all operator applications.
    Filter by status: pending, approved, rejected
    """
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(OperatorApplication)

    if status:
        query = query.filter(OperatorApplication.status == status)

    applications = query.order_by(OperatorApplication.created_at.desc()).all()

    return [
        {
            "id": app.id,
            "company_name": app.company_name,
            "contact_name": app.contact_name,
            "contact_phone": app.contact_phone,
            "contact_email": app.contact_email,
            "business_registration_number": app.business_registration_number,
            "country": app.country,
            "city": app.city,
            "address": app.address,
            "description": app.description,
            "status": app.status,
            "admin_notes": app.admin_notes,
            "created_at": app.created_at,
            "reviewed_at": app.reviewed_at,
        }
        for app in applications
    ]


class ApproveApplicationRequest(BaseModel):
    application_id: int
    admin_notes: Optional[str] = None


@router.post("/operator-applications/approve")
def approve_operator_application(
    payload: ApproveApplicationRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Approve an operator application and send OTP for password setup
    """
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    # Find application
    application = db.query(OperatorApplication).filter(
        OperatorApplication.id == payload.application_id
    ).first()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Application already {application.status}"
        )

    # Check if phone already registered
    existing_user = db.query(User).filter(
        User.phone == application.contact_phone
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Phone number already registered"
        )

    # Update application status (don't create user yet)
    application.status = "approved"
    application.admin_notes = payload.admin_notes
    application.approved_by = user.id
    application.reviewed_at = datetime.now()

    db.commit()
    db.refresh(application)

    # Send OTP to operator's phone for password setup
    from app.utils.sms_utils import generate_otp, send_otp_sms, format_phone_number, get_otp_expiry
    from app.models import OTPVerification

    formatted_phone = format_phone_number(application.contact_phone)

    # Invalidate any previous OTPs for this phone
    db.query(OTPVerification).filter(
        OTPVerification.phone == formatted_phone,
        OTPVerification.purpose == "operator_setup",
        OTPVerification.is_verified == False
    ).update({"is_verified": True})
    db.commit()

    # Generate and save new OTP
    otp_code = generate_otp()
    expires_at = get_otp_expiry()

    otp_record = OTPVerification(
        phone=formatted_phone,
        otp_code=otp_code,
        purpose="operator_setup",
        expires_at=expires_at,
        is_verified=False
    )
    db.add(otp_record)
    db.commit()

    # Send SMS with OTP
    sms_sent = send_otp_sms(
        formatted_phone,
        otp_code,
        "operator_setup"
    )

    return {
        "success": True,
        "message": f"Application approved! An OTP has been sent to {formatted_phone} to set up the operator account.",
        "application_id": application.id,
        "phone": formatted_phone,
        "otp_sent": sms_sent
    }


class RejectApplicationRequest(BaseModel):
    application_id: int
    admin_notes: str  # Reason for rejection


@router.post("/operator-applications/reject")
def reject_operator_application(
    payload: RejectApplicationRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Reject an operator application
    """
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    # Find application
    application = db.query(OperatorApplication).filter(
        OperatorApplication.id == payload.application_id
    ).first()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Application already {application.status}"
        )

    # Update application status
    application.status = "rejected"
    application.admin_notes = payload.admin_notes
    application.approved_by = user.id
    application.reviewed_at = datetime.now()

    db.commit()

    return {
        "success": True,
        "message": f"Application for '{application.company_name}' rejected",
        "application_id": application.id
    }

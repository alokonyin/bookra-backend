from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta, timezone
import uuid

from app.database import get_db
from app.models import Office, OfficeInvite, User, Trip, Booking, Payment
from app.schemas import (
    OfficeCreate,
    OfficeUpdate,
    OfficeOut,
    OfficeInviteCreate,
    OfficeInviteOut,
    OfficeUserSignup,
)
from app.routers.auth import get_current_user, hash_password

router = APIRouter(prefix="/v1/offices", tags=["Offices"])


# ======================================================
# 🏢 Office Dashboard (for office role users)
# ======================================================
@router.get("/dashboard")
def office_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dashboard for office users showing only their office's data"""
    if current_user.role != "office":
        raise HTTPException(status_code=403, detail="Only office users can access this dashboard")

    if not current_user.office_id:
        raise HTTPException(status_code=400, detail="User is not associated with an office")

    try:
        # Get office info
        office = db.query(Office).filter(Office.id == current_user.office_id).first()
        if not office:
            raise HTTPException(status_code=404, detail="Office not found")

        # Get trips for this office only
        trips = db.query(Trip).filter(Trip.office_id == current_user.office_id).all()
        trip_ids = [t.id for t in trips]

        total_trips = len(trips)
        total_bookings = db.query(Booking).filter(Booking.trip_id.in_(trip_ids)).count() if trip_ids else 0

        # Seats sold
        seats_sold = (
            db.query(func.sum(Booking.passengers))
            .filter(Booking.trip_id.in_(trip_ids))
            .scalar()
            or 0
        ) if trip_ids else 0

        # Revenue for this office
        office_revenue = (
            db.query(func.sum(Payment.amount))
            .join(Booking, Payment.booking_id == Booking.id)
            .filter(
                Payment.status == "success",
                Booking.trip_id.in_(trip_ids),
            )
            .scalar()
            or 0
        ) if trip_ids else 0

        # Recent bookings for this office
        recent_bookings = (
            db.query(Booking)
            .filter(Booking.trip_id.in_(trip_ids))
            .order_by(Booking.created_at.desc())
            .limit(5)
            .all()
        ) if trip_ids else []

        booking_list = [
            {
                "id": b.id,
                "trip_id": b.trip_id,
                "trip": {
                    "from_city": b.trip.from_city,
                    "to_city": b.trip.to_city,
                    "date": b.trip.date.isoformat(),
                    "time": b.trip.time.isoformat(),
                },
                "passengers": b.passengers,
                "total_amount": b.total_amount,
                "status": b.status,
                "contact_email": b.contact_email,
                "contact_phone": b.contact_phone,
                "created_at": b.created_at,
            }
            for b in recent_bookings
        ]

        return {
            "office_id": office.id,
            "office_name": office.office_name,
            "city": office.city,
            "total_trips": total_trips,
            "total_bookings": total_bookings,
            "seats_sold": seats_sold,
            "revenue": round(office_revenue, 2),
            "recent_bookings": booking_list,
        }

    except Exception as e:
        print("❌ Office dashboard error:", e)
        raise HTTPException(status_code=500, detail="Failed to load office dashboard")


# ======================================================
# 1️⃣ Create Office (Operator only)
# ======================================================
@router.post("/", response_model=OfficeOut)
def create_office(
    payload: OfficeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new office for the current operator"""
    if current_user.role != "operator":
        raise HTTPException(status_code=403, detail="Only operators can create offices")

    # Check if email already exists
    existing = db.query(Office).filter(Office.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Office email already exists")

    office = Office(
        operator_id=current_user.id,
        office_name=payload.office_name,
        city=payload.city,
        email=payload.email,
        phone=payload.phone,
        address=payload.address,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    db.add(office)
    db.commit()
    db.refresh(office)

    return office


# ======================================================
# 2️⃣ List Operator's Offices
# ======================================================
@router.get("/", response_model=List[OfficeOut])
def list_offices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all offices for the current operator"""
    if current_user.role != "operator":
        raise HTTPException(status_code=403, detail="Only operators can view offices")

    offices = (
        db.query(Office)
        .filter(Office.operator_id == current_user.id)
        .order_by(Office.created_at.desc())
        .all()
    )

    return offices


# ======================================================
# 3️⃣ Get Single Office
# ======================================================
@router.get("/{office_id}", response_model=OfficeOut)
def get_office(
    office_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific office by ID"""
    office = db.query(Office).filter(Office.id == office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    # Check access: operator owns the office
    if current_user.role == "operator" and office.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Office users can only see their own office
    if current_user.role == "office" and current_user.office_id != office_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return office


# ======================================================
# 4️⃣ Update Office (Operator only)
# ======================================================
@router.patch("/{office_id}", response_model=OfficeOut)
def update_office(
    office_id: int,
    payload: OfficeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update office details (operator only)"""
    if current_user.role != "operator":
        raise HTTPException(
            status_code=403, detail="Only operators can update offices"
        )

    office = db.query(Office).filter(Office.id == office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    if office.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update fields
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(office, field, value)

    db.commit()
    db.refresh(office)

    return office


# ======================================================
# 5️⃣ Delete Office (Operator only)
# ======================================================
@router.delete("/{office_id}")
def delete_office(
    office_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an office (soft delete by marking inactive)"""
    if current_user.role != "operator":
        raise HTTPException(
            status_code=403, detail="Only operators can delete offices"
        )

    office = db.query(Office).filter(Office.id == office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    if office.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Soft delete by marking inactive
    office.is_active = False
    db.commit()

    return {"message": "Office deactivated successfully"}


# ======================================================
# 6️⃣ Generate Office Invite (Operator only)
# ======================================================
@router.post("/invites", response_model=OfficeInviteOut)
def generate_office_invite(
    payload: OfficeInviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate an invite link for an office"""
    if current_user.role != "operator":
        raise HTTPException(
            status_code=403, detail="Only operators can generate invites"
        )

    # Verify office belongs to operator
    office = db.query(Office).filter(Office.id == payload.office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    if office.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Generate UUID token
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)

    invite = OfficeInvite(
        office_id=payload.office_id,
        token=token,
        email=payload.email,
        expires_at=expires_at,
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
    )

    db.add(invite)
    db.commit()
    db.refresh(invite)

    return invite


# ======================================================
# 7️⃣ List Office Invites
# ======================================================
@router.get("/invites/list", response_model=List[OfficeInviteOut])
def list_office_invites(
    office_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all invites for operator's offices"""
    if current_user.role != "operator":
        raise HTTPException(
            status_code=403, detail="Only operators can view invites"
        )

    query = db.query(OfficeInvite).join(Office).filter(
        Office.operator_id == current_user.id
    )

    if office_id:
        query = query.filter(OfficeInvite.office_id == office_id)

    invites = query.order_by(OfficeInvite.created_at.desc()).all()

    return invites


# ======================================================
# 8️⃣ Accept Office Invite (Public - no auth required)
# ======================================================
@router.post("/invites/accept")
def accept_office_invite(
    payload: OfficeUserSignup,
    db: Session = Depends(get_db),
):
    """Accept an office invite and create office user account"""
    # Find the invite
    invite = db.query(OfficeInvite).filter(OfficeInvite.token == payload.token).first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite token")

    if invite.used_at:
        raise HTTPException(status_code=400, detail="Invite already used")

    if datetime.now(timezone.utc) > invite.expires_at:
        raise HTTPException(status_code=400, detail="Invite has expired")

    # Get the office
    office = db.query(Office).filter(Office.id == invite.office_id).first()
    if not office or not office.is_active:
        raise HTTPException(status_code=400, detail="Office not found or inactive")

    # Use invite email if user doesn't provide one
    email = payload.email or invite.email
    phone = payload.phone

    if not email and not phone:
        raise HTTPException(
            status_code=400, detail="Either email or phone must be provided"
        )

    # Check if user already exists
    if email:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

    if phone:
        existing = db.query(User).filter(User.phone == phone).first()
        if existing:
            raise HTTPException(status_code=400, detail="Phone already registered")

    # Create office user
    user = User(
        role="office",
        email=email,
        phone=phone,
        password_hash=hash_password(payload.password),
        name=payload.name,
        office_id=invite.office_id,
        created_at=datetime.now(timezone.utc),
    )

    db.add(user)

    # Mark invite as used
    invite.used_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    return {
        "message": "Office user account created successfully",
        "user_id": user.id,
        "office_id": invite.office_id,
        "email": user.email,
    }


# ======================================================
# 9️⃣ Revoke Office Invite
# ======================================================
@router.delete("/invites/{invite_id}")
def revoke_office_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke/delete an office invite"""
    if current_user.role != "operator":
        raise HTTPException(
            status_code=403, detail="Only operators can revoke invites"
        )

    invite = db.query(OfficeInvite).filter(OfficeInvite.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    # Verify office belongs to operator
    office = db.query(Office).filter(Office.id == invite.office_id).first()
    if office.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(invite)
    db.commit()

    return {"message": "Invite revoked successfully"}

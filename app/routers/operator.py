from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models import Trip, Booking, PaymentMethod, Payment, User, Office
from app.schemas import TripCreate, TripOut, PaymentMethodCreate, PaymentMethodOut
from app.routers.auth import get_current_user


router = APIRouter(prefix="/v1/operator", tags=["Operator"])

# -------------------------------------------------------------------
# 1️⃣ Operator Dashboard (updated)
# -------------------------------------------------------------------
@router.get("/dashboard")
def operator_dashboard(user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "operator":
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # 1️⃣ Get operator's trips
        trips = db.query(Trip).filter(Trip.operator_id == user.id).all()
        trip_ids = [t.id for t in trips]

        total_trips = len(trips)

        # Handle case where operator has no trips yet
        if not trip_ids:
            return {
                "total_trips": 0,
                "total_bookings": 0,
                "seats_sold": 0,
                "revenue": 0.0,
                "platform_revenue": 0.0,
                "recent_payments": [],
                "offices": [],
                "total_offices": db.query(Office).filter(Office.operator_id == user.id).count(),
            }

        total_bookings = db.query(Booking).filter(Booking.trip_id.in_(trip_ids)).count()

        # 2️⃣ Seats sold
        seats_sold = (
            db.query(func.sum(Booking.passengers))
            .filter(Booking.trip_id.in_(trip_ids))
            .scalar()
            or 0
        )

        # 3️⃣ Operator's revenue (95% of successful payments for their trips)
        total_payment_amount = (
            db.query(func.sum(Payment.amount))
            .join(Booking, Payment.booking_id == Booking.id)
            .filter(
                Payment.status == "success",
                Booking.trip_id.in_(trip_ids)
            )
            .scalar()
            or 0
        )
        total_revenue = total_payment_amount * 0.95  # Operator gets 95%

        # 4️⃣ Platform (admin) share (5%)
        platform_revenue = total_payment_amount * 0.05

        # 5️⃣ Recent operator payments
        recent_payments = (
            db.query(Payment.id, Payment.amount, Payment.method, Payment.status,
                    Payment.transaction_id, Payment.created_at)
            .join(Booking, Payment.booking_id == Booking.id)
            .filter(Booking.trip_id.in_(trip_ids))
            .order_by(Payment.created_at.desc())
            .limit(5)
            .all()
        )

        payment_list = [
            {
                "id": p.id,
                "amount": p.amount or 0,
                "method": p.method or "",
                "status": p.status or "",
                "transaction_id": p.transaction_id or "",
                "timestamp": str(p.created_at) if p.created_at else None,
            }
            for p in recent_payments
        ]

        # 6️⃣ Office breakdown
        offices = db.query(Office).filter(Office.operator_id == user.id).all()
        office_stats = []

        for office in offices:
            office_trips = [t for t in trips if t.office_id == office.id]
            office_trip_ids = [t.id for t in office_trips]

            office_bookings = db.query(Booking).filter(
                Booking.trip_id.in_(office_trip_ids)
            ).count() if office_trip_ids else 0

            office_payment_total = (
                db.query(func.sum(Payment.amount))
                .join(Booking, Payment.booking_id == Booking.id)
                .filter(
                    Payment.status == "success",
                    Booking.trip_id.in_(office_trip_ids),
                )
                .scalar()
                or 0
            ) if office_trip_ids else 0
            office_revenue = office_payment_total * 0.95  # Operator gets 95%

            office_stats.append({
                "office_id": office.id,
                "office_name": office.office_name,
                "city": office.city,
                "trips": len(office_trips),
                "bookings": office_bookings,
                "revenue": round(office_revenue, 2),
                "is_active": office.is_active,
            })

        return {
            "total_trips": total_trips,
            "total_bookings": total_bookings,
            "seats_sold": seats_sold,
            "revenue": round(total_revenue, 2),
            "platform_revenue": round(platform_revenue, 2),
            "recent_payments": payment_list,
            "offices": office_stats,
            "total_offices": len(offices),
        }

    except Exception as e:
        print("❌ Operator dashboard error:", e)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load operator dashboard: {str(e)}")



# -------------------------------------------------------------------
# 2️⃣ Create New Trip
# -------------------------------------------------------------------
@router.post("/trips", response_model=TripOut)
def create_trip(
    payload: TripCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.role not in ["operator", "office"]:
        raise HTTPException(status_code=403, detail="Only operators and office users can create trips")

    # Validate office_id
    office = db.query(Office).filter(Office.id == payload.office_id).first()
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")

    # Operator can create trips for any of their offices
    if user.role == "operator":
        if office.operator_id != user.id:
            raise HTTPException(status_code=403, detail="Office does not belong to you")
    # Office users can only create trips for their assigned office
    elif user.role == "office":
        if user.office_id != payload.office_id:
            raise HTTPException(status_code=403, detail="You can only create trips for your assigned office")

    new_trip = Trip(
        operator_id=office.operator_id,  # Always use the office's operator_id
        office_id=payload.office_id,
        mode=payload.mode,
        from_city=payload.from_city,
        to_city=payload.to_city,
        date=payload.date,
        time=payload.time,
        price=payload.price,
        total_seats=payload.total_seats,
        seats_available=payload.total_seats,
        created_at=datetime.utcnow(),
    )

    db.add(new_trip)
    db.commit()
    db.refresh(new_trip)
    return new_trip



# -------------------------------------------------------------------
# 3️⃣ List All Trips
# -------------------------------------------------------------------
@router.get("/trips", response_model=List[TripOut])
def list_trips(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "operator":
        # Operators see all their trips
        return db.query(Trip).filter(Trip.operator_id == user.id).all()
    elif user.role == "office":
        # Office users see only their office's trips
        if not user.office_id:
            raise HTTPException(status_code=400, detail="Office ID not assigned")
        return db.query(Trip).filter(Trip.office_id == user.office_id).all()
    else:
        raise HTTPException(status_code=403, detail="Access denied")


# -------------------------------------------------------------------
# 4️⃣ Get Bookings for an Operator’s Trips
# -------------------------------------------------------------------
@router.get("/bookings")
def get_operator_bookings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == "operator":
        # Operators see bookings for all their trips
        trips = db.query(Trip).filter(Trip.operator_id == user.id).all()
    elif user.role == "office":
        # Office users see bookings only for their office's trips
        if not user.office_id:
            raise HTTPException(status_code=400, detail="Office ID not assigned")
        trips = db.query(Trip).filter(Trip.office_id == user.office_id).all()
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not trips:
        return []

    trip_ids = [t.id for t in trips]
    bookings = db.query(Booking).filter(Booking.trip_id.in_(trip_ids)).all()

    results = []
    for b in bookings:
        trip = db.query(Trip).filter(Trip.id == b.trip_id).first()
        office = db.query(Office).filter(Office.id == trip.office_id).first() if trip else None

        results.append({
            "id": b.id,
            "trip_id": b.trip_id,
            "contact_email": b.contact_email,
            "contact_phone": b.contact_phone,
            "seat_numbers": b.seat_numbers,
            "passengers": b.passengers,
            "total_amount": b.total_amount,
            "status": b.status,
            "created_at": b.created_at,
            "trip_details": {
                "id": trip.id if trip else None,
                "from_city": trip.from_city if trip else None,
                "to_city": trip.to_city if trip else None,
                "date": trip.date.isoformat() if trip and trip.date else None,
                "time": trip.time.isoformat() if trip and trip.time else None,
                "office": {
                    "id": office.id if office else None,
                    "name": office.office_name if office else "Unknown Office",
                } if office else None,
            },
        })
    return results


# -------------------------------------------------------------------
# 5️⃣ Payment Method Setup
# -------------------------------------------------------------------
@router.post("/payment-method", response_model=PaymentMethodOut)
def add_payment_method(payload: PaymentMethodCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "operator":
        raise HTTPException(status_code=403, detail="Access denied")

    existing = db.query(PaymentMethod).filter(PaymentMethod.operator_id == user.id).first()
    if existing:
        existing.account_name = payload.account_name
        existing.account_number = payload.account_number
        existing.bank_name = payload.bank_name
    else:
        existing = PaymentMethod(operator_id=user.id, **payload.dict())
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


@router.get("/payment-method", response_model=PaymentMethodOut)
def get_payment_method(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "operator":
        raise HTTPException(status_code=403, detail="Access denied")

    pm = db.query(PaymentMethod).filter(PaymentMethod.operator_id == user.id).first()
    if not pm:
        raise HTTPException(status_code=404, detail="Payment method not found")

    return pm


# -------------------------------------------------------------------
# 6️⃣ Operator Profile Management
# -------------------------------------------------------------------
class OperatorProfileUpdate(BaseModel):
    name: Optional[str] = None
    company_name: Optional[str] = None
    logo_url: Optional[str] = None


@router.get("/me")
def get_operator_me(user: User = Depends(get_current_user)):
    if user.role != "operator":
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "company_name": user.company_name,
        "logo_url": user.logo_url,
    }


@router.patch("/profile")
def update_operator_profile(
    payload: OperatorProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.role != "operator":
        raise HTTPException(status_code=403, detail="Not authorized")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return {"message": "Profile updated", "user": user}


# -------------------------------------------------------------------
# 7️⃣ Update Trip
# -------------------------------------------------------------------
@router.put("/trips/{trip_id}")
def update_trip(trip_id: int, payload: TripCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "operator":
        raise HTTPException(status_code=403, detail="Not authorized")

    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.operator_id == user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    for key, value in payload.dict().items():
        setattr(trip, key, value)

    db.commit()
    db.refresh(trip)
    return trip

# -------------------------------------------------------------------
# 8️⃣ Get a Single Trip (for Edit)
# -------------------------------------------------------------------
@router.get("/trips/{trip_id}", response_model=TripOut)
def get_trip(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "operator":
        raise HTTPException(status_code=403, detail="Not authorized")

    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.operator_id == user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    return trip


# -------------------------------------------------------------------
# 9️⃣ Delete Trip
# -------------------------------------------------------------------
@router.delete("/trips/{trip_id}")
def delete_trip(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "operator":
        raise HTTPException(status_code=403, detail="Not authorized")

    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.operator_id == user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    db.delete(trip)
    db.commit()

    return {"message": "Trip deleted successfully"}

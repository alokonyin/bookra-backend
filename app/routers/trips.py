from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Trip, Booking, User

router = APIRouter(prefix="/v1/trips", tags=["Trips"])


# ------------------------------
# 🔹 Get all trips (optional)
# ------------------------------
@router.get("/")
def list_trips(db: Session = Depends(get_db)):
    trips = db.query(Trip).options(joinedload(Trip.operator)).all()
    return [
        {
            "id": t.id,
            "from_city": t.from_city,
            "to_city": t.to_city,
            "date": str(t.date),
            "time": str(t.time),
            "price": t.price,
            "total_seats": t.total_seats,
            "seats_available": t.seats_available,
            "operator": {
                "id": t.operator.id if t.operator else None,
                "name": (
                    t.operator.name
                    or t.operator.company_name
                    or t.operator.email
                    if t.operator else None
                ),
                "logo_url": t.operator.logo_url if t.operator else None,
            } if t.operator else None,
        }
        for t in trips
    ]


# ------------------------------
# 🔹 Get single trip (includes booked seats)
# ------------------------------
@router.get("/{trip_id}")
def get_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(Trip).options(joinedload(Trip.operator)).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # 🔸 Collect all booked seats for this trip
    bookings = db.query(Booking).filter(Booking.trip_id == trip.id, Booking.status != "cancelled").all()
    booked_seats = []
    for b in bookings:
        if b.seat_numbers:
            # seat_numbers could be list or comma-separated string
            if isinstance(b.seat_numbers, list):
                booked_seats.extend(b.seat_numbers)
            elif isinstance(b.seat_numbers, str):
                booked_seats.extend([s.strip() for s in b.seat_numbers.split(",") if s.strip()])

    return {
        "id": trip.id,
        "operator_id": trip.operator_id,
        "mode": trip.mode,
        "from_city": trip.from_city,
        "to_city": trip.to_city,
        "date": str(trip.date),
        "time": str(trip.time),
        "price": trip.price,
        "total_seats": trip.total_seats,
        "seats_available": trip.seats_available,
        "booked_seats": list(set(booked_seats)),  # ✅ unique + returned to frontend
        "operator": {
            "id": trip.operator.id if trip.operator else None,
            "name": (
                trip.operator.name
                or trip.operator.company_name
                or trip.operator.email
                if trip.operator else None
            ),
            "company_name": trip.operator.company_name if trip.operator else None,
            "logo_url": trip.operator.logo_url if trip.operator else None,
        } if trip.operator else None,
    }

@router.get("/{trip_id}")
def get_trip_by_id(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # ✅ Return clean structured response
    return {
        "id": trip.id,
        "from_city": trip.from_city,
        "to_city": trip.to_city,
        "date": str(trip.date),
        "time": str(trip.time),
        "mode": trip.mode,
        "price": float(trip.price),
        "total_seats": trip.total_seats,
        "operator_id": trip.operator_id,
    }

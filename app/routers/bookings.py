from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.database import get_db
from app.models import Booking, Trip, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/v1/bookings", tags=["Bookings"])

# ---------------------------------------------------
# Create Booking with Passenger Details
# ---------------------------------------------------
@router.post("/create")
def create_booking_with_details(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a pending booking with passenger details"""
    if current_user.role != "traveler":
        raise HTTPException(status_code=403, detail="Only travelers can create bookings")

    trip_id = payload.get("trip_id")
    seat_numbers = payload.get("seat_numbers", [])
    amount = payload.get("amount")
    passenger_details = payload.get("passenger_details", {})

    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if trip.seats_available < len(seat_numbers):
        raise HTTPException(status_code=400, detail="Not enough seats available")

    # Create booking with status="pending"
    # Handle empty strings for date field - convert to None
    dob = passenger_details.get("date_of_birth")
    if dob == "":
        dob = None

    booking = Booking(
        traveler_id=current_user.id,
        trip_id=trip.id,
        seat_numbers=seat_numbers,
        passengers=len(seat_numbers),
        total_amount=amount,
        # Passenger details
        passenger_title=passenger_details.get("title") or None,
        passenger_first_name=passenger_details.get("first_name") or None,
        passenger_middle_name=passenger_details.get("middle_name") or None,
        passenger_last_name=passenger_details.get("last_name") or None,
        passenger_dob=dob,
        passenger_nationality=passenger_details.get("nationality") or None,
        passenger_document_type=passenger_details.get("document_type") or None,
        passenger_document_number=passenger_details.get("document_number") or None,
        # Contact details
        contact_email=payload.get("contact_email") or None,
        contact_phone=payload.get("contact_phone") or None,
        contact_address=payload.get("contact_address") or None,
        contact_city=payload.get("contact_city") or None,
        contact_country=payload.get("contact_country") or None,
        status="pending",  # Pending until payment
        created_at=datetime.utcnow(),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return {
        "message": "Booking created successfully",
        "booking_id": booking.id,
        "status": "pending",
        "total_amount": booking.total_amount,
    }

# ---------------------------------------------------
# Get Single Booking by ID
# ---------------------------------------------------
@router.get("/{booking_id}")
def get_booking_by_id(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get booking details with trip information"""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check access
    if current_user.role == "traveler" and booking.traveler_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    trip = db.query(Trip).filter(Trip.id == booking.trip_id).first()

    return {
        "id": booking.id,
        "trip_id": booking.trip_id,
        "passengers": booking.passengers,
        "total_amount": booking.total_amount,
        "seat_numbers": booking.seat_numbers,
        "status": booking.status,
        "created_at": booking.created_at,
        "trip": {
            "id": trip.id,
            "from_city": trip.from_city,
            "to_city": trip.to_city,
            "date": str(trip.date),
            "time": str(trip.time),
            "mode": trip.mode,
        } if trip else None,
    }

# ---------------------------------------------------
# 1️⃣ Create Booking (Traveler books a trip)
# ---------------------------------------------------
@router.post("/", response_model=dict)
def create_booking(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "traveler":
        raise HTTPException(status_code=403, detail="Only travelers can book trips")

    trip_id = payload.get("trip_id")
    passengers = payload.get("passengers", 1)
    contact_email = payload.get("contact_email")
    contact_phone = payload.get("contact_phone")

    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.seats_available < passengers:
        raise HTTPException(status_code=400, detail="Not enough seats available")

    # Update available seats
    trip.seats_available -= passengers

    booking = Booking(
        traveler_id=current_user.id,
        trip_id=trip.id,
        passengers=passengers,
        total_amount=trip.price * passengers,
        contact_email=contact_email,
        contact_phone=contact_phone,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return {
        "message": "Booking created successfully",
        "booking_id": booking.id,
        "trip_id": trip.id,
        "total_amount": booking.total_amount,
    }

# ---------------------------------------------------
# 2️⃣ List Traveler Bookings
# ---------------------------------------------------
@router.get("/", response_model=List[dict])
def list_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "traveler":
        raise HTTPException(status_code=403, detail="Only travelers can view bookings")

    bookings = (
        db.query(Booking)
        .filter(Booking.traveler_id == current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )

    return [
        {
            "id": b.id,
            "trip_id": b.trip_id,
            "passengers": b.passengers,
            "total_amount": b.total_amount,
            "status": b.status,
            "created_at": b.created_at,
        }
        for b in bookings
    ]


@router.get("")
def get_bookings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Role-based booking visibility:
    - Traveler: their own bookings
    - Operator: bookings on their trips
    - Admin: all bookings
    """
    q = db.query(Booking)

    if current_user.role == "traveler":
        q = q.filter(Booking.traveler_id == current_user.id)

    elif current_user.role == "operator":
        # Join through trip to find bookings for operator’s trips
        q = q.join(Trip).filter(Trip.operator_id == current_user.id)

    elif current_user.role == "admin":
        pass  # all bookings

    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    bookings = q.order_by(Booking.created_at.desc()).all()
    return bookings



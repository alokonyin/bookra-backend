from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime, date as date_type
from app.database import get_db
from app.models import Trip, Booking, Payment, User
from app.schemas import BookingCreate, BookingOut, PaymentCreate, PaymentOut
from app.routers.auth import get_current_user
from app.utils.email_utils import send_booking_email

router = APIRouter(prefix="/v1/traveler", tags=["Traveler"])

# ======================================================
# 1️⃣ Search Trips (with operator info)
# ======================================================
@router.get("/search", response_model=List[dict])
def search_trips(
    from_city: Optional[str] = Query(None, description="Departure city"),
    to_city: Optional[str] = Query(None, description="Destination city"),
    date: Optional[str] = Query(None, description="Travel date (YYYY-MM-DD)"),
    mode: Optional[str] = Query(None, description="bus/flight/etc."),
    db: Session = Depends(get_db),
):
    """
    Traveler trip search.
    Includes operator info and safely handles missing/invalid date filters.
    """

    query = db.query(Trip).options(joinedload(Trip.operator))

    # Apply filters
    if from_city:
        query = query.filter(Trip.from_city.ilike(from_city))
    if to_city:
        query = query.filter(Trip.to_city.ilike(to_city))

    # 🗓 Handle date filtering (parse string safely)
    if date not in (None, "", "null"):
        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(Trip.date == parsed_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format (YYYY-MM-DD)")
    else:
        # If no date given → show upcoming trips from today onward
        today = datetime.utcnow().date()
        query = query.filter(Trip.date >= today)

    if mode:
        query = query.filter(Trip.mode == mode)

    trips = query.order_by(Trip.date, Trip.time).all()
    if not trips:
        raise HTTPException(status_code=404, detail="No trips found")

    return [
        {
            "id": t.id,
            "operator_id": t.operator_id,
            "mode": t.mode,
            "from_city": t.from_city,
            "to_city": t.to_city,
            "date": str(t.date),
            "time": str(t.time),
            "price": t.price,
            "seats_available": t.seats_available,
            # ✅ Operator info (name > company > email)
            "operator": {
                "id": t.operator.id if t.operator else None,
                "name": (
                    t.operator.name
                    or t.operator.company_name
                    or t.operator.email
                    if t.operator else None
                ),
                "company_name": t.operator.company_name if t.operator else None,
                "logo_url": t.operator.logo_url if t.operator else None,
            } if t.operator else None,
        }
        for t in trips
    ]

@router.get("/my-trips")
def get_my_trips(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Returns all bookings for the logged-in traveler.
    """
    bookings = (
        db.query(Booking)
        .filter(Booking.traveler_id == user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )

    results = []
    for b in bookings:
        trip = db.query(Trip).filter(Trip.id == b.trip_id).first()
        results.append(
            {
                "booking_id": b.id,
                "trip_id": b.trip_id,
                "from_city": trip.from_city if trip else None,
                "to_city": trip.to_city if trip else None,
                "date": trip.date if trip else None,
                "time": trip.time if trip else None,
                "status": b.status,
                "seat_numbers": b.seat_numbers,
                "total_amount": b.total_amount,
                "created_at": b.created_at,
            }
        )
    return results

# ======================================================
# 2️⃣ Create Booking
# ======================================================
# ------------------------------
# 2️⃣ Create booking (with seat validation)
# ------------------------------
# ------------------------------
# 2️⃣ Create booking (partial booking fallback)
# ------------------------------
@router.post("/bookings", response_model=BookingOut)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # 1️⃣ Verify trip exists
    trip = db.query(Trip).filter(Trip.id == payload.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # 2️⃣ Fetch all non-cancelled bookings for this trip
    active_bookings = (
        db.query(Booking)
        .filter(Booking.trip_id == trip.id, Booking.status != "cancelled")
        .all()
    )

    booked = set()
    for b in active_bookings:
        if b.seat_numbers:
            if isinstance(b.seat_numbers, list):
                booked.update(b.seat_numbers)
            elif isinstance(b.seat_numbers, str):
                booked.update([s.strip() for s in b.seat_numbers.split(",") if s.strip()])

    # 3️⃣ Determine which seats are available vs taken
    requested = set(payload.seat_numbers)
    taken = booked.intersection(requested)
    free = requested - taken

    if not free:
        raise HTTPException(
            status_code=400,
            detail=f"All requested seats are already booked: {', '.join(sorted(taken))}",
        )

    # 4️⃣ Adjust passengers count and total price for free seats only
    passengers = len(free)
    total_amount = passengers * trip.price

    # 5️⃣ Create booking for available seats only
    booking = Booking(
        traveler_id=user.id,
        trip_id=payload.trip_id,
        passengers=passengers,
        total_amount=total_amount,
        seat_numbers=list(free),
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        status="pending",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # 6️⃣ Update seat availability
    trip.seats_available = max(trip.seats_available - passengers, 0)
    db.commit()

    # 7️⃣ Return success with notice
    message = (
        f"Booking confirmed for {passengers} seat(s): {', '.join(sorted(free))}."
    )
    if taken:
        message += f" The following seats were already booked: {', '.join(sorted(taken))}."

    return {
        **booking.__dict__,
        "message": message,
        "booked": list(sorted(free)),
        "unavailable": list(sorted(taken)),
    }



# ======================================================
# 3️⃣ View My Bookings
# ======================================================
@router.get("/bookings/me", response_model=List[BookingOut])
def my_bookings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Booking).filter(Booking.traveler_id == user.id).all()


# ======================================================
# 4️⃣ Initiate Payment (mock Flutterwave)
# ======================================================
@router.post("/payments/initiate", response_model=PaymentOut)
def initiate_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payment = Payment(
        booking_id=payload.booking_id,
        method=payload.method,
        amount=payload.amount,
        status="initiated",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


# ======================================================
# 5️⃣ Verify Payment + Send Email
# ======================================================
@router.post("/payments/verify/{booking_id}", response_model=PaymentOut)
def verify_payment(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    payment = db.query(Payment).filter(Payment.booking_id == booking_id).first()
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Simulate payment success
    if payment:
        payment.status = "success"
    booking.status = "completed"
    db.commit()

    # Email confirmation asynchronously
    if booking.contact_email:
        # Use passenger name or contact email as fallback
        recipient_name = booking.passenger_first_name or booking.contact_email
        background_tasks.add_task(
            send_booking_email,
            booking.contact_email,
            recipient_name,
            booking.total_amount,
            booking.trip,
        )

    db.refresh(payment)
    return payment


# ======================================================
# 6️⃣ Cancel Booking
# ======================================================
@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id, Booking.traveler_id == user.id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status == "completed":
        raise HTTPException(status_code=400, detail="Cannot cancel a completed booking")

    booking.status = "cancelled"
    trip = db.query(Trip).filter(Trip.id == booking.trip_id).first()
    if trip:
        trip.seats_available += booking.passengers
    db.commit()

    return {"message": "Booking cancelled and seats restored"}

@router.get("/trips/{trip_id}/booked-seats")
def get_booked_seats(trip_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Returns all seat numbers already booked for this trip.
    Travelers can use this to avoid selecting taken seats.
    """
    # Optional: ensure traveler only
    if user.role != "traveler":
        raise HTTPException(status_code=403, detail="Only travelers can view booked seats")

    bookings = db.query(Booking).filter(Booking.trip_id == trip_id).all()
    booked = []
    for b in bookings:
        if b.seat_numbers:
            booked.extend(b.seat_numbers)

    return {"booked_seats": booked}

# ======================================================
# 7️⃣ Get Trip Details (for confirmation page)
# ======================================================
@router.get("/../trips/{trip_id}")
def get_trip_details(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Returns details of a specific trip (for traveler confirmation page).
    Includes mode (bus/flight), price, seat count, and operator info.
    """
    trip = (
        db.query(Trip)
        .options(joinedload(Trip.operator))
        .filter(Trip.id == trip_id)
        .first()
    )

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Include operator info if available
    operator_info = None
    if trip.operator:
        operator_info = {
            "id": trip.operator.id,
            "name": trip.operator.name or trip.operator.company_name or trip.operator.email,
            "company_name": trip.operator.company_name,
            "logo_url": trip.operator.logo_url,
        }

    return {
        "id": trip.id,
        "from_city": trip.from_city,
        "to_city": trip.to_city,
        "date": str(trip.date),
        "time": str(trip.time),
        "price": float(trip.price),
        "total_seats": trip.total_seats,
        "seats_available": trip.seats_available,
        "mode": trip.mode,
        "operator": operator_info,
    }

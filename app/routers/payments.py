from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.database import get_db
from ..models import Payment, Booking, Trip, User
from ..schemas import PaymentCreate
from app.routers.auth import get_current_user
# from app.security import get_current_user
from datetime import datetime

router = APIRouter(prefix="/v1/payments", tags=["payments"])

@router.get("/ping")
def ping():
    return {"status": "ok", "message": "payments router active"}

@router.post("/process")
def process_payment(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process payment for a pending booking.
    Marks booking as completed and splits payment between admin and operator.
    """
    if current_user.role != "traveler":
        raise HTTPException(status_code=403, detail="Only travelers can make payments")

    booking_id = payload.get("booking_id")
    method = payload.get("method", "mock")  # card, mpesa, mock

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.traveler_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if booking.status == "completed":
        raise HTTPException(status_code=400, detail="Booking already paid")

    # Get trip and update seat availability
    trip = db.query(Trip).filter(Trip.id == booking.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    trip.seats_available -= booking.passengers

    # Get operator and admin
    operator = db.query(User).filter(User.id == trip.operator_id).first()
    admin = db.query(User).filter(User.role == "admin").first()

    # Split payment: 95% operator, 5% admin
    operator_amount = round(booking.total_amount * 0.95, 2)
    admin_amount = round(booking.total_amount * 0.05, 2)

    # Create payment records
    now = datetime.utcnow()
    payments = [
        Payment(
            booking_id=booking.id,
            payer_id=current_user.id,
            receiver_id=operator.id if operator else None,
            role="operator",
            method=method,
            amount=operator_amount,
            status="success",
            transaction_id=f"TXN-{int(now.timestamp())}-OP",
            created_at=now,
        ),
        Payment(
            booking_id=booking.id,
            payer_id=current_user.id,
            receiver_id=admin.id if admin else None,
            role="admin",
            method=method,
            amount=admin_amount,
            status="success",
            transaction_id=f"TXN-{int(now.timestamp())}-AD",
            created_at=now,
        ),
    ]
    db.add_all(payments)

    # Mark booking as completed
    booking.status = "completed"

    db.commit()

    return {
        "status": "success",
        "message": "Payment processed successfully",
        "booking_id": booking.id,
        "operator_amount": operator_amount,
        "admin_amount": admin_amount,
    }

@router.post("")
def process_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mock payment processor:
    - Splits 5% Admin / 95% Operator
    - Marks booking as completed
    - Decrements seat count on Trip
    """

    booking = db.query(Booking).filter(Booking.id == payload.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status == "completed":
        raise HTTPException(status_code=400, detail="Booking already paid")

    # ✅ Find the trip
    trip = db.query(Trip).filter(Trip.id == booking.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # ✅ Compute split
    admin_share = round(booking.total_amount * 0.05, 2)
    operator_share = round(booking.total_amount * 0.95, 2)

    # ✅ Identify admin & operator
    admin_user = db.query(User).filter(User.role == "admin").first()
    if not admin_user:
        raise HTTPException(status_code=400, detail="Admin account missing")

    if not hasattr(trip, "operator_id"):
        raise HTTPException(status_code=400, detail="Trip missing operator_id")
    operator_user = db.query(User).filter(User.id == trip.operator_id).first()
    if not operator_user:
        raise HTTPException(status_code=400, detail="Operator not found")

    # ✅ Create payment records (split)
    now = datetime.utcnow()
    payments = [
        Payment(
            booking_id=booking.id,
            payer_id=booking.traveler_id,
            receiver_id=admin_user.id,
            role="admin",
            method=payload.method,
            amount=admin_share,
            status="success",
            transaction_id=f"ADM-{int(now.timestamp())}",
        ),
        Payment(
            booking_id=booking.id,
            payer_id=booking.traveler_id,
            receiver_id=operator_user.id,
            role="operator",
            method=payload.method,
            amount=operator_share,
            status="success",
            transaction_id=f"OPR-{int(now.timestamp())}",
        ),
    ]

    db.add_all(payments)

    # ✅ Mark booking as completed
    booking.status = "completed"

    # ✅ Decrease available seats on trip
    if hasattr(trip, "available_seats") and trip.available_seats >= booking.passengers:
        trip.available_seats -= booking.passengers
    elif hasattr(trip, "available_seats"):
        trip.available_seats = 0  # in case of overflow

    db.commit()

    for p in payments:
        db.refresh(p)

    return {"message": "Payment successful", "split": [p.__dict__ for p in payments]}


@router.post("/mock")
def mock_payment(payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Simulates a successful payment.
    - Only travelers can make this call.
    - Creates a Booking (status = completed)
    - Splits payment 95% to operator, 5% to admin.
    """
    if user.role != "traveler":
        raise HTTPException(status_code=403, detail="Only travelers can make payments")

    # ✅ Validate trip exists
    trip = db.query(Trip).filter(Trip.id == payload["trip_id"]).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # ✅ Check available seats
    if trip.seats_available < len(payload["seat_numbers"]):
        raise HTTPException(status_code=400, detail="Not enough seats available")

    # ✅ Extract passenger details
    passenger_details = payload.get("passenger_details", {})

    # ✅ Create the booking
    new_booking = Booking(
        traveler_id=user.id,  # ✅ fixed field name
        trip_id=trip.id,
        seat_numbers=payload["seat_numbers"],
        # Passenger details
        passenger_title=passenger_details.get("title"),
        passenger_first_name=passenger_details.get("first_name"),
        passenger_middle_name=passenger_details.get("middle_name"),
        passenger_last_name=passenger_details.get("last_name"),
        passenger_dob=passenger_details.get("date_of_birth"),
        passenger_nationality=passenger_details.get("nationality"),
        passenger_document_type=passenger_details.get("document_type"),
        passenger_document_number=passenger_details.get("document_number"),
        # Contact details
        contact_email=payload.get("contact_email"),
        contact_phone=payload.get("contact_phone"),
        contact_address=payload.get("contact_address"),
        contact_city=payload.get("contact_city"),
        contact_country=payload.get("contact_country"),
        passengers=len(payload["seat_numbers"]),
        total_amount=payload["amount"],
        status="completed",
        created_at=datetime.utcnow(),
    )
    db.add(new_booking)

    # ✅ Update trip seat availability
    trip.seats_available -= len(payload["seat_numbers"])

    # ✅ Get operator & admin
    operator = db.query(User).filter(User.id == trip.operator_id).first()
    admin = db.query(User).filter(User.role == "admin").first()

    # ✅ Split the payment
    operator_amount = round(payload["amount"] * 0.95, 2)
    admin_amount = round(payload["amount"] * 0.05, 2)

    # ✅ Create Payment records
    payments = [
        Payment(
            booking_id=new_booking.id,
            receiver_id=operator.id if operator else None,
            amount=operator_amount,
            method="mock",
            status="success",
            role="operator",
            transaction_id=f"MOCK-{datetime.utcnow().timestamp()}",
            created_at=datetime.utcnow(),
        ),
        Payment(
            booking_id=new_booking.id,
            receiver_id=admin.id if admin else None,
            amount=admin_amount,
            method="mock",
            status="success",
            role="admin",
            transaction_id=f"MOCK-{datetime.utcnow().timestamp()}",
            created_at=datetime.utcnow(),
        ),
    ]
    db.add_all(payments)

    # ✅ Commit everything together
    db.commit()
    db.refresh(new_booking)

    return {
        "status": "success",
        "message": "Mock payment completed successfully",
        "booking_id": new_booking.id,
        "operator_amount": operator_amount,
        "admin_amount": admin_amount,
        "remaining_seats": trip.seats_available,
    }


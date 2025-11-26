from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    func,
    UniqueConstraint,
    Date,
    Time,
    Float,
    ForeignKey,
    ARRAY,
    Boolean,
)
from sqlalchemy.dialects.postgresql import ENUM
from .database import Base
import enum
from sqlalchemy.orm import relationship
from datetime import datetime


# -------------------------------------------------------
# Enums
# -------------------------------------------------------
class RoleEnum(str, enum.Enum):
    traveler = "traveler"
    operator = "operator"
    admin = "admin"
    office = "office"


# -------------------------------------------------------
# User
# -------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone = Column(String, unique=True, nullable=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(ENUM(RoleEnum, name="role_enum", create_type=True, validate_strings=True), nullable=False, index=True)

    # Office relationship (for office role users)
    office_id = Column(Integer, ForeignKey("offices.id"), nullable=True, index=True)

    # Operator fields
    name = Column(String, nullable=True)
    company_name = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)

    # Traveler-specific fields
    title = Column(String, nullable=True)  # Mr, Mrs, Ms, Dr
    first_name = Column(String, nullable=True)
    middle_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    nationality = Column(String, nullable=True)
    document_type = Column(String, nullable=True)  # passport, national_id, drivers_license
    document_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payment_method = relationship("PaymentMethod", back_populates="operator", uselist=False)
    trips = relationship("Trip", back_populates="operator", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="traveler", cascade="all, delete-orphan")

    # Office relationships
    offices = relationship("Office", foreign_keys="Office.operator_id", back_populates="operator")
    office = relationship("Office", foreign_keys="[User.office_id]", back_populates="office_users")

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("phone", name="uq_users_phone"),
    )


# -------------------------------------------------------
# Trip (created by Operator)
# -------------------------------------------------------
class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey("users.id"))
    office_id = Column(Integer, ForeignKey("offices.id"), nullable=True, index=True)
    mode = Column(Enum("bus", "flight", name="trip_mode"), nullable=False)
    from_city = Column(String, nullable=False)
    to_city = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    price = Column(Float, nullable=False)
    total_seats = Column(Integer, nullable=False)
    seats_available = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ✅ Back-link
    operator = relationship("User", back_populates="trips")
    office = relationship("Office", back_populates="trips")
    bookings = relationship("Booking", back_populates="trip", cascade="all, delete-orphan")


# -------------------------------------------------------
# Booking (made by Traveler)
# -------------------------------------------------------
class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    traveler_id = Column(Integer, ForeignKey("users.id"))
    trip_id = Column(Integer, ForeignKey("trips.id"))
    passengers = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=False)
    seat_numbers = Column(ARRAY(String))                #seat_numbers = Column(String)
    status = Column(Enum("pending", "completed", "cancelled", name="booking_status"), default="pending")

    # Passenger details
    passenger_title = Column(String, nullable=True)
    passenger_first_name = Column(String, nullable=True)
    passenger_middle_name = Column(String, nullable=True)
    passenger_last_name = Column(String, nullable=True)
    passenger_dob = Column(Date, nullable=True)
    passenger_nationality = Column(String, nullable=True)
    passenger_document_type = Column(String, nullable=True)
    passenger_document_number = Column(String, nullable=True)

    # Contact details
    contact_email = Column(String)
    contact_phone = Column(String)
    contact_address = Column(String, nullable=True)
    contact_city = Column(String, nullable=True)
    contact_country = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # ✅ Relationships
    trip = relationship("Trip", back_populates="bookings")
    traveler = relationship("User", back_populates="bookings")
    payments = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")


# -------------------------------------------------------
# Payment
# -------------------------------------------------------
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    method = Column(Enum("momo", "mpesa", "card", "mock", name="payment_method"))
    status = Column(Enum("initiated", "success", "failed", name="payment_status"), default="initiated")
    amount = Column(Float)
    transaction_id = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    booking = relationship("Booking", back_populates="payments")


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey("users.id"))
    account_name = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    bank_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    operator = relationship("User", back_populates="payment_method")


# -------------------------------------------------------
# Office (branch of an operator)
# -------------------------------------------------------
class Office(Base):
    __tablename__ = "offices"

    id = Column(Integer, primary_key=True, index=True)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    office_name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    operator = relationship("User", foreign_keys=[operator_id], back_populates="offices")
    office_users = relationship("User", foreign_keys="User.office_id", back_populates="office")
    trips = relationship("Trip", back_populates="office")
    invites = relationship("OfficeInvite", back_populates="office", cascade="all, delete-orphan")


# -------------------------------------------------------
# Office Invite (UUID-based invite system)
# -------------------------------------------------------
class OfficeInvite(Base):
    __tablename__ = "office_invites"

    id = Column(Integer, primary_key=True, index=True)
    office_id = Column(Integer, ForeignKey("offices.id"), nullable=False, index=True)
    token = Column(String(36), unique=True, nullable=False, index=True)
    email = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    office = relationship("Office", back_populates="invites")


class VerifiedOperator(Base):
    __tablename__ = "verified_operators"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    company_domain = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    verified_by_admin = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    country = Column(String, nullable=True)
    __table_args__ = (
    UniqueConstraint('company_name', name='uq_verified_operator_company'),
)


# -------------------------------------------------------
# OTP Verification (for phone-based auth)
# -------------------------------------------------------
class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, nullable=False, index=True)
    otp_code = Column(String(6), nullable=False)
    purpose = Column(String, nullable=False)  # 'signup', 'signin', 'password_reset'
    is_verified = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)


# -------------------------------------------------------
# Operator Application (for manual approval workflow)
# -------------------------------------------------------
class OperatorApplication(Base):
    __tablename__ = "operator_applications"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    contact_name = Column(String, nullable=False)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=False, index=True)
    business_registration_number = Column(String, nullable=True)
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    address = Column(String, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String, default="pending")  # 'pending', 'approved', 'rejected'
    admin_notes = Column(String, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)




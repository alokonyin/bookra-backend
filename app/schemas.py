from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Literal, List
from datetime import date, time, datetime

RoleLiteral = Literal["traveler", "operator", "admin", "office"]

class SignupIn(BaseModel):
    role: RoleLiteral
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str
    name: Optional[str] = None
    company_name: Optional[str] = None
    logo_url: Optional[str] = None

    @field_validator("email", "phone", mode="before")
    @classmethod
    def empty_to_none(cls, v):
        return v or None

    @field_validator("password")
    @classmethod
    def password_len(cls, v):
        if len(v) < 6:
            raise ValueError("password must be at least 6 characters")
        return v

    @field_validator("phone")
    @classmethod
    def phone_ok(cls, v, info):
        if v is None and info.data.get("email") is None:
            raise ValueError("Provide email or phone")
        return v


class LoginIn(BaseModel):
    identifier: str  # email or phone
    password: str

class UserOut(BaseModel):
    id: int
    role: RoleLiteral
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    office_id: Optional[int] = None  # ✅ Added for office users

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class TripOut(BaseModel):
    id: int
    from_city: str
    to_city: str
    date: date
    time: time
    price: float
    total_seats: int
    seats_available: int
    mode: str
    created_at: datetime

    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    trip_id: int
    passengers: int
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    seat_numbers: List[str]
    total_amount: float

class BookingOut(BaseModel):
    id: int
    trip: TripOut
    passengers: int
    total_amount: float
    status: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    created_at: datetime
    class Config:
        orm_mode = True

class PaymentCreate(BaseModel):
    booking_id: int
    method: str
    amount: float

class PaymentOut(BaseModel):
    id: int
    status: str
    method: str
    amount: float
    transaction_id: Optional[str]
    timestamp: datetime
    class Config:
        orm_mode = True


# --- Operator Trip Schemas ---
class TripCreate(BaseModel):
    from_city: str
    to_city: str
    date: date
    time: time
    price: float
    total_seats: int
    mode: str  # ✅ "bus" or "flight"
    office_id: int  # ✅ Required - trip must be assigned to an office

class TripOut(TripCreate):
    id: int
    seats_available: int
    created_at: datetime
    class Config:
        from_attributes = True

# --- Payment Schemas ---
class PaymentMethodCreate(BaseModel):
    account_name: str
    account_number: str
    bank_name: str

class PaymentMethodOut(PaymentMethodCreate):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True


class VerifiedOperatorBase(BaseModel):
    company_name: str
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    country: Optional[str] = None


class VerifiedOperatorCreate(BaseModel):
    company_name: str
    company_domain: Optional[str] = None  # 🆕
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    class Config:
        from_attributes = True


class VerifiedOperatorOut(BaseModel):
    id: int
    company_name: str
    company_domain: Optional[str] = None  # 🆕
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    verified_by_admin: bool
    created_at: datetime

    class Config:
        orm_mode = True


class PaymentMethodCreate(BaseModel):
    bank_name: str
    account_name: str
    account_number: str

    class Config:
        from_attributes = True


class PaymentMethodOut(BaseModel):
    id: int
    bank_name: str
    account_name: str
    account_number: str

    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    trip_id: Optional[int] = None          # For traveler mock payments
    booking_id: Optional[int] = None       # For existing bookings
    seat_numbers: Optional[List[str]] = [] # For seat selection
    amount: float
    method: Optional[str] = "mock"
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

class PaymentOut(BaseModel):
    id: int
    booking_id: int
    payer_id: int
    receiver_id: int
    role: str
    amount: float
    status: str
    transaction_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Office Schemas ---
class OfficeCreate(BaseModel):
    office_name: str
    city: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class OfficeUpdate(BaseModel):
    office_name: Optional[str] = None
    city: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None

class OfficeOut(BaseModel):
    id: int
    operator_id: int
    office_name: str
    city: str
    email: str
    phone: Optional[str]
    address: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- Office Invite Schemas ---
class OfficeInviteCreate(BaseModel):
    office_id: int
    email: Optional[EmailStr] = None
    expires_in_hours: int = 72  # Default 3 days

class OfficeInviteOut(BaseModel):
    id: int
    office_id: int
    token: str
    email: Optional[str]
    expires_at: datetime
    used_at: Optional[datetime]
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Office User Signup Schema ---
class OfficeUserSignup(BaseModel):
    token: str
    password: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_len(cls, v):
        if len(v) < 6:
            raise ValueError("password must be at least 6 characters")
        return v

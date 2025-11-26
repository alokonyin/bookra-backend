from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from app.models import Trip

conf = ConnectionConfig(
    MAIL_USERNAME="your_email@example.com",
    MAIL_PASSWORD="your_app_password",
    MAIL_FROM="no-reply@bookra.africa",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,      # ✅ replaces MAIL_TLS
    MAIL_SSL_TLS=False,      # ✅ replaces MAIL_SSL
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_booking_email(to_email: EmailStr, name: str, amount: float, trip: Trip):
    subject = f"Your Bookra Booking Confirmation — {trip.from_city} → {trip.to_city}"
    body = f"""
    Hello {name},

    Your booking has been confirmed.

    Trip: {trip.from_city} → {trip.to_city}
    Date: {trip.date} {trip.time}
    Amount Paid: ${amount}

    Thank you for choosing Bookra.
    """
    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=body,
        subtype="plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)

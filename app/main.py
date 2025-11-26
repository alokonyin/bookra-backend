import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routers import auth, trips, traveler, operator, admin, bookings, payments, offices, otp

app = FastAPI(title="Bookra API")
Base.metadata.create_all(bind=engine)


# Allow trusted origins (support environment variable for production)
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

# Apply CORS policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(otp.router)
app.include_router(trips.router)
app.include_router(bookings.router)
app.include_router(operator.router)
app.include_router(traveler.router)
app.include_router(admin.router)
app.include_router(payments.router)
app.include_router(offices.router)

# Health check endpoint
@app.get("/health")
def health():
    return {"ok": True}


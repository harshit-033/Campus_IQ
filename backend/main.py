from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import qrcode

from database import engine, Base, SessionLocal
import models
import uuid
from fastapi import HTTPException
import os
import joblib
model = joblib.load("ai/attendance_model.pkl")

app = FastAPI(title="CampusIQ API")



Base.metadata.create_all(bind=engine)



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def home():
    return {"message": "CampusIQ Backend Running"}



@app.post("/register")
def register_user(
    name: str,
    email: str,
    password: str,
    role: str = "student",
    db: Session = Depends(get_db)
):

    user = models.User(
        name=name,
        email=email,
        password=password,
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "User registered successfully", "user_id": user.id}



@app.post("/create-event")
def create_event(
    title: str,
    description: str,
    venue: str,
    fee: float,
    participant_limit: int,
    db: Session = Depends(get_db)
):

    event = models.Event(
        title=title,
        description=description,
        venue=venue,
        fee=fee,
        participant_limit=participant_limit
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return {"message": "Event created successfully", "event_id": event.id}



@app.get("/events")
def get_events(db: Session = Depends(get_db)):

    events = db.query(models.Event).all()

    return events


@app.get("/generate-qr/{event_id}")
def generate_qr(event_id: int):

    data = f"CampusIQ Event ID: {event_id}"

    img = qrcode.make(data)

    filename = f"event_{event_id}_qr.png"

    img.save(filename)

    return {"message": "QR code generated", "file": filename}





@app.post("/register-event")
def register_event(user_id: int, event_id: int, db: Session = Depends(get_db)):

    # Check if event exists
    event = db.query(models.Event).filter(models.Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Check if event is full
    total_registered = db.query(models.Registration).filter(
        models.Registration.event_id == event_id
    ).count()

    if total_registered >= event.participant_limit:
        raise HTTPException(status_code=400, detail="Event is full")

    # Check duplicate registration
    existing = db.query(models.Registration).filter(
        models.Registration.user_id == user_id,
        models.Registration.event_id == event_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already registered")

    qr_token = str(uuid.uuid4())

    registration = models.Registration(
        user_id=user_id,
        event_id=event_id,
        qr_code=qr_token
    )

    db.add(registration)
    db.commit()
    db.refresh(registration)

    # Generate QR Code
    qr_data = f"TICKET:{qr_token}"

    img = qrcode.make(qr_data)

    filename = f"{qr_token}.png"
    filepath = os.path.join("qr_codes", filename)

    img.save(filepath)

    return {
        "message": "Event registered successfully",
        "qr_token": qr_token,
        "qr_image": filepath
    }

@app.post("/scan-ticket")
def scan_ticket(qr_token: str, db: Session = Depends(get_db)):

    registration = db.query(models.Registration).filter(
        models.Registration.qr_code == qr_token
    ).first()

    if not registration:
        raise HTTPException(status_code=404, detail="Invalid Ticket")

    if registration.checked_in:
        raise HTTPException(status_code=400, detail="Ticket already used")

    registration.checked_in = True
    db.commit()

    return {
        "message": "Entry Allowed",
        "registration_id": registration.id
    }

@app.get("/event-stats/{event_id}")
def event_stats(event_id: int, db: Session = Depends(get_db)):

    event = db.query(models.Event).filter(models.Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    total_registered = db.query(models.Registration).filter(
        models.Registration.event_id == event_id
    ).count()

    checked_in = db.query(models.Registration).filter(
        models.Registration.event_id == event_id,
        models.Registration.checked_in == True
    ).count()

    remaining_seats = event.participant_limit - total_registered

    return {
        "event_id": event_id,
        "total_registered": total_registered,
        "checked_in": checked_in,
        "remaining_seats": remaining_seats
    }
@app.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):

    total_events = db.query(models.Event).count()

    total_registrations = db.query(models.Registration).count()

    registrations = db.query(models.Registration).all()

    total_revenue = 0

    for reg in registrations:
        event = db.query(models.Event).filter(models.Event.id == reg.event_id).first()
        if event:
            total_revenue += event.fee

    return {
        "total_events": total_events,
        "total_registrations": total_registrations,
        "total_revenue": total_revenue
    }

@app.get("/dashboard/event-details/{event_id}")
def event_details(event_id: int, db: Session = Depends(get_db)):

    event = db.query(models.Event).filter(models.Event.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    registrations = db.query(models.Registration).filter(
        models.Registration.event_id == event_id
    ).count()

    checked_in = db.query(models.Registration).filter(
        models.Registration.event_id == event_id,
        models.Registration.checked_in == True
    ).count()

    revenue = registrations * event.fee

    return {
        "event_id": event.id,
        "title": event.title,
        "registrations": registrations,
        "checked_in": checked_in,
        "revenue": revenue
    }
@app.get("/ai/predict-attendance/{event_id}")
def predict_attendance(event_id:int, db:Session=Depends(get_db)):

    event = db.query(models.Event).filter(models.Event.id==event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    registrations = db.query(models.Registration).filter(
        models.Registration.event_id==event_id
    ).count()

    prediction = model.predict([[event.participant_limit,event.fee,registrations]])

    predicted_attendance = int(prediction[0])

    return {
        "event_id": event_id,
        "predicted_attendance": predicted_attendance
    }
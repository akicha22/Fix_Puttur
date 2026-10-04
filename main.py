"""
FixPuttur - civic complaint backend (FastAPI + SQLite + SQLAlchemy)

Run it with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Then open http://localhost:8000/docs to try every endpoint.
"""

import math
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base, relationship, selectinload, sessionmaker

# ----------------------------------------------------------------------------
# 1. SETTINGS
# ----------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent          # folder that contains main.py
UPLOAD_DIR = BASE_DIR / "uploads"                    # photos are saved here
UPLOAD_DIR.mkdir(exist_ok=True)
DB_URL = f"sqlite:///{(BASE_DIR / 'fixputtur.db').as_posix()}"

MERGE_RADIUS_M = 50                                  # reports within 50 m are merged
MAX_PHOTO_BYTES = 5 * 1024 * 1024                    # 5 MB
ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
STATUSES = ("open", "in_progress", "resolved")

# category -> (severity, department)
CATEGORIES = {
    "open manhole": (10, "Roads"),
    "water leak": (7, "Water Supply"),
    "pothole": (6, "Roads"),
    "streetlight": (4, "Electricity"),
    "garbage": (3, "Sanitation"),
    "request/suggestion": (2, "General"),
}

# PINs come from environment variables: PIN_ROADS, PIN_WATER_SUPPLY, PIN_ELECTRICITY,
# PIN_SANITATION, PIN_GENERAL. The fallback values are for local testing ONLY.
_DEFAULT_PINS = {"Roads": "1111", "Water Supply": "2222", "Electricity": "3333",
                 "Sanitation": "4444", "General": "5555"}
DEPT_PINS = {d: os.environ.get("PIN_" + d.upper().replace(" ", "_"), p)
             for d, p in _DEFAULT_PINS.items()}
if DEPT_PINS == _DEFAULT_PINS:
    print("WARNING: using default test PINs. Set the PIN_* environment variables before going live.")

MAX_TEXT = 1000          # longest allowed description / note
FAILED_PINS = {}         # ip address -> times of recent wrong PINs


# ----------------------------------------------------------------------------
# 2. DATABASE SETUP AND TABLES
# ----------------------------------------------------------------------------

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def utcnow():
    """Current UTC time (without timezone info, which is what SQLite stores)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="open", index=True)
    report_count = Column(Integer, nullable=False, default=1)
    upvotes = Column(Integer, nullable=False, default=0)
    near_sensitive = Column(Boolean, nullable=False, default=False)
    department = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    priority_score = Column(Float, nullable=False, default=0)

    reports = relationship("Report", order_by="Report.id")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False, index=True)
    reporter_phone = Column(String, nullable=False)
    note = Column(Text)
    photo_path = Column(String)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class Upvote(Base):
    __tablename__ = "upvotes"
    # The database itself refuses a second upvote from the same phone.
    __table_args__ = (UniqueConstraint("issue_id", "phone", name="one_upvote_per_phone"),)

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False, index=True)
    phone = Column(String, nullable=False)


class StatusLog(Base):
    __tablename__ = "status_log"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False, index=True)
    old_status = Column(String, nullable=False)
    new_status = Column(String, nullable=False)
    note = Column(Text)
    changed_at = Column(DateTime, nullable=False, default=utcnow)


Base.metadata.create_all(bind=engine)  # creates the tables if they don't exist


def get_db():
    """Gives each request its own database session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------------------------------------------------------
# 3. HELPER FUNCTIONS
# ----------------------------------------------------------------------------

def haversine_m(lat1, lng1, lat2, lng2):
    """Distance in metres between two GPS points (great-circle / haversine)."""
    r = 6371000  # Earth radius in metres
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def days_open(issue, now):
    """Days since the issue was created. Resolved issues stop counting (0)."""
    if issue.status == "resolved":
        return 0.0
    return max(0.0, (now - issue.created_at).total_seconds() / 86400)


def compute_priority(issue, now):
    severity = CATEGORIES[issue.category][0]
    score = (
        issue.report_count * 3
        + issue.upvotes * 1
        + severity * 5
        + days_open(issue, now) * 2
        + (10 if issue.near_sensitive else 0)
    )
    return round(score, 1)


def escalation_level(days):
    if days > 7:
        return 2
    if days > 3:
        return 1
    return 0


def issue_to_dict(issue, now):
    days = days_open(issue, now)
    return {
        "id": issue.id,
        "category": issue.category,
        "description": issue.description,
        "lat": issue.lat,
        "lng": issue.lng,
        "status": issue.status,
        "report_count": issue.report_count,
        "upvotes": issue.upvotes,
        "near_sensitive": issue.near_sensitive,
        "department": issue.department,
        "created_at": issue.created_at.isoformat() + "Z",
        "priority_score": issue.priority_score,
        "days_open": round(days, 1),
        "escalation_level": escalation_level(days),
        "photos": [r.photo_path for r in issue.reports if r.photo_path],
    }


def serialize_and_sort(db: Session, issues):
    """Refresh each issue's priority (it changes as days pass), then sort high -> low."""
    now = utcnow()
    result = []
    for issue in issues:
        issue.priority_score = compute_priority(issue, now)
        result.append(issue_to_dict(issue, now))
    db.commit()  # saves the refreshed scores
    result.sort(key=lambda item: (-item["priority_score"], item["id"]))
    return result


def clean_category(raw: str) -> str:
    category = raw.strip().lower()
    if category not in CATEGORIES:
        raise HTTPException(400, f"Unknown category. Choose one of: {', '.join(CATEGORIES)}")
    return category


def clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) < 10:
        raise HTTPException(400, "Please enter a valid 10-digit phone number")
    return digits[-10:]  # keep the last 10 digits so +91 / 0 prefixes don't matter


def get_issue_or_404(db: Session, issue_id: int) -> Issue:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(404, "Issue not found")
    return issue


# ----------------------------------------------------------------------------
# 4. THE APP + STATIC FILES
# ----------------------------------------------------------------------------

app = FastAPI(title="FixPuttur API")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/", include_in_schema=False)
def home():
    index = BASE_DIR / "index.html"
    if not index.exists():
        raise HTTPException(404, "index.html not found next to main.py")
    return FileResponse(index)


# ----------------------------------------------------------------------------
# 5. ENDPOINTS
# ----------------------------------------------------------------------------

@app.post("/reports")
def create_report(
    category: str = Form(...),
    description: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    phone: str = Form(...),
    near_sensitive: bool = Form(False),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    category = clean_category(category)
    phone = clean_phone(phone)
    description = description.strip()
    if not description:
        raise HTTPException(400, "Description cannot be empty")
    if len(description) > MAX_TEXT:
        raise HTTPException(400, f"Description is too long (max {MAX_TEXT} characters)")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(400, "lat/lng are out of range")

    # --- save the photo (optional) ---
    photo_path = None
    if photo is not None and photo.filename:
        ext = Path(photo.filename).suffix.lower()
        if ext not in ALLOWED_PHOTO_EXT:
            raise HTTPException(400, "Photo must be .jpg, .jpeg, .png or .webp")
        data = photo.file.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "Photo is too big (max 5 MB)")
        is_img = (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"
                  or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"))
        if not is_img:  # the file name can lie, the first bytes can't
            raise HTTPException(400, "That file is not a real image")
        filename = f"{uuid.uuid4().hex}{ext}"  # random name, so nobody can overwrite files
        (UPLOAD_DIR / filename).write_bytes(data)
        photo_path = f"/uploads/{filename}"

    # --- look for an OPEN issue of the SAME category within 50 m ---
    now = utcnow()
    dlat = MERGE_RADIUS_M * 1.5 / 111000  # cheap box around the pin so we don't scan every issue
    dlng = dlat / max(math.cos(math.radians(lat)), 0.01)
    candidates = db.query(Issue).filter(
        Issue.status == "open", Issue.category == category,
        Issue.lat.between(lat - dlat, lat + dlat), Issue.lng.between(lng - dlng, lng + dlng),
    ).all()
    nearest, nearest_dist = None, None
    for c in candidates:
        dist = haversine_m(lat, lng, c.lat, c.lng)
        if dist <= MERGE_RADIUS_M and (nearest is None or dist < nearest_dist):
            nearest, nearest_dist = c, dist

    if nearest is not None:
        if db.query(Report).filter_by(issue_id=nearest.id, reporter_phone=phone).first():
            if photo_path:  # don't leave an orphan photo behind
                (UPLOAD_DIR / Path(photo_path).name).unlink(missing_ok=True)
            raise HTTPException(409, f"You already reported this problem (issue #{nearest.id}). "
                                     "Use 'I'm affected' on the board instead.")
        issue = nearest
        merged = True
        issue.report_count += 1
        if near_sensitive:
            issue.near_sensitive = True  # one report mentioning a school/hospital is enough
    else:
        _, department = CATEGORIES[category]
        issue = Issue(
            category=category,
            description=description,
            lat=lat,
            lng=lng,
            status="open",
            report_count=1,
            upvotes=0,
            near_sensitive=near_sensitive,
            department=department,
            created_at=now,
        )
        db.add(issue)
        db.flush()  # gives the new issue its id
        merged = False

    report = Report(
        issue_id=issue.id,
        reporter_phone=phone,
        note=description,
        photo_path=photo_path,
        created_at=now,
    )
    db.add(report)
    issue.priority_score = compute_priority(issue, now)
    db.commit()
    db.refresh(issue)

    return {
        "merged": merged,
        "issue_id": issue.id,
        "report_id": report.id,
        "report_count": issue.report_count,
        "distance_m": round(nearest_dist, 1) if merged else None,
        "message": (
            "Added to an existing issue nearby" if merged else "New issue created"
        ),
        "issue": issue_to_dict(issue, now),
    }


@app.get("/issues")
def list_issues(
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Issue).options(selectinload(Issue.reports))
    if category:
        query = query.filter(Issue.category == clean_category(category))
    if status:
        status = status.strip().lower()
        if status not in STATUSES:
            raise HTTPException(400, f"status must be one of: {', '.join(STATUSES)}")
        query = query.filter(Issue.status == status)
    return serialize_and_sort(db, query.all())


class PhoneBody(BaseModel):
    phone: str


@app.post("/issues/{issue_id}/upvote")
def upvote_issue(issue_id: int, body: PhoneBody, db: Session = Depends(get_db)):
    phone = clean_phone(body.phone)
    issue = get_issue_or_404(db, issue_id)

    already = db.query(Upvote).filter_by(issue_id=issue_id, phone=phone).first()
    if already:
        raise HTTPException(409, "This phone number has already upvoted this issue")

    db.add(Upvote(issue_id=issue_id, phone=phone))
    issue.upvotes += 1
    issue.priority_score = compute_priority(issue, utcnow())
    try:
        db.commit()
    except IntegrityError:  # two taps at the same moment - the database caught it
        db.rollback()
        raise HTTPException(409, "This phone number has already upvoted this issue")

    return {"issue_id": issue_id, "upvotes": issue.upvotes, "priority_score": issue.priority_score}


class StatusBody(BaseModel):
    status: str
    note: Optional[str] = None


@app.patch("/issues/{issue_id}/status")
def update_status(
    issue_id: int,
    body: StatusBody,
    request: Request,
    x_dept_pin: Optional[str] = Header(None),  # read from the "X-Dept-Pin" header
    db: Session = Depends(get_db),
):
    issue = get_issue_or_404(db, issue_id)

    # Lock out an address after 5 wrong PINs in 10 minutes (stops PIN guessing).
    ip = request.client.host if request.client else "?"
    now_t = time.time()
    recent = [t for t in FAILED_PINS.get(ip, []) if now_t - t < 600]
    if len(recent) >= 5:
        raise HTTPException(429, "Too many wrong PINs. Try again in 10 minutes.")

    # The PIN must belong to the department that owns this issue.
    correct_pin = DEPT_PINS.get(issue.department, "")
    if not x_dept_pin or not correct_pin or not secrets.compare_digest(
        x_dept_pin.encode(), correct_pin.encode()
    ):
        FAILED_PINS[ip] = recent + [now_t]
        raise HTTPException(401, "Missing or wrong X-Dept-Pin for this department")
    FAILED_PINS.pop(ip, None)

    new_status = body.status.strip().lower()
    if new_status not in STATUSES:
        raise HTTPException(400, f"status must be one of: {', '.join(STATUSES)}")
    if new_status == issue.status:
        raise HTTPException(400, f"Issue is already '{new_status}'")

    old_status = issue.status
    issue.status = new_status
    db.add(
        StatusLog(
            issue_id=issue.id,
            old_status=old_status,
            new_status=new_status,
            note=(body.note or "")[:MAX_TEXT] or None,
        )
    )
    issue.priority_score = compute_priority(issue, utcnow())
    db.commit()

    return {"issue_id": issue_id, "old_status": old_status, "new_status": new_status}


@app.get("/issues/{issue_id}/history")
def issue_history(issue_id: int, db: Session = Depends(get_db)):
    get_issue_or_404(db, issue_id)
    rows = db.query(StatusLog).filter_by(issue_id=issue_id).order_by(StatusLog.id).all()
    return [{"old_status": r.old_status, "new_status": r.new_status, "note": r.note,
             "changed_at": r.changed_at.isoformat() + "Z"} for r in rows]


@app.get("/dept/{name}/issues")
def department_issues(name: str, db: Session = Depends(get_db)):
    if name.strip().lower() not in {d.lower() for d in DEPT_PINS}:
        raise HTTPException(404, f"Unknown department. Choose one of: {', '.join(DEPT_PINS)}")
    issues = db.query(Issue).options(selectinload(Issue.reports)).filter(func.lower(Issue.department) == name.strip().lower()).all()
    return serialize_and_sort(db, issues)


@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    def count_status(status):
        return db.query(func.count(Issue.id)).filter(Issue.status == status).scalar()

    return {
        "total_issues": db.query(func.count(Issue.id)).scalar(),
        "open": count_status("open"),
        "in_progress": count_status("in_progress"),
        "resolved": count_status("resolved"),
        "total_reports": db.query(func.count(Report.id)).scalar(),
    }


# ----------------------------------------------------------------------------
# 6. SAMPLE DATA  (made-up complaints scattered around 12.766, 75.200)
# ----------------------------------------------------------------------------

# (category, description, lat, lng, near_sensitive, status, days_ago, reports, upvotes)
SAMPLE_ISSUES = [
    ("open manhole", "Manhole cover missing on the main road, right outside a school gate", 12.7662, 75.2008, True, "open", 5, 4, 12),
    ("open manhole", "Broken manhole cover near the bus stand, bikes swerving around it", 12.7711, 75.1954, False, "in_progress", 2, 2, 6),
    ("water leak", "Main pipe leaking and flooding the road for days", 12.7589, 75.2041, False, "open", 9, 3, 8),
    ("water leak", "Water leaking from a pipe beside the hospital entrance", 12.7634, 75.2103, True, "open", 3, 2, 5),
    ("water leak", "Tap point overflowing in the market lane", 12.7748, 75.2062, False, "resolved", 6, 1, 2),
    ("water leak", "Pipe joint leaking at the junction, water wasted all day", 12.7552, 75.1987, False, "open", 1, 1, 0),
    ("pothole", "Deep pothole at the junction, two-wheelers skidding", 12.7681, 75.2019, False, "open", 8, 5, 14),
    ("pothole", "Series of potholes after the rain on the service road", 12.7620, 75.1923, False, "open", 4, 3, 7),
    ("pothole", "Large pothole in front of a hospital, ambulances have to slow down", 12.7705, 75.2148, True, "in_progress", 6, 2, 9),
    ("pothole", "Road edge crumbled near the school bus stop", 12.7573, 75.2090, True, "open", 2, 1, 4),
    ("pothole", "Small potholes along the lane near the temple road", 12.7790, 75.2005, False, "resolved", 10, 1, 1),
    ("streetlight", "Streetlight not working for two weeks, very dark at night", 12.7645, 75.1978, False, "open", 12, 3, 6),
    ("streetlight", "Flickering light near the school playground", 12.7608, 75.2066, True, "open", 3, 1, 2),
    ("streetlight", "Pole light broken after a storm", 12.7727, 75.2121, False, "in_progress", 5, 2, 3),
    ("streetlight", "Whole lane is dark, three lights out in a row", 12.7541, 75.2033, False, "open", 0, 1, 1),
    ("garbage", "Garbage heap piling up beside the market, bad smell", 12.7699, 75.2037, False, "open", 7, 4, 10),
    ("garbage", "Uncollected waste near the school wall", 12.7656, 75.2132, True, "open", 2, 2, 4),
    ("garbage", "Roadside dumping spot growing near the bridge", 12.7582, 75.1951, False, "resolved", 4, 2, 3),
    ("garbage", "Overflowing public dustbin, stray dogs scattering waste", 12.7738, 75.1991, False, "open", 1, 1, 0),
    ("request/suggestion", "Please add a speed breaker near the school crossing", 12.7617, 75.2014, True, "open", 4, 2, 8),
]


@app.post("/seed")
def seed(db: Session = Depends(get_db)):
    if db.query(func.count(Issue.id)).scalar() > 0:
        return {"seeded": False, "message": "Database already has issues, so seeding was skipped."}

    now = utcnow()
    fake_phone_counter = 0  # makes unique fake phone numbers: 9000000001, 9000000002, ...

    for (category, description, lat, lng, sensitive, status,
         days_ago, n_reports, n_upvotes) in SAMPLE_ISSUES:
        _, department = CATEGORIES[category]
        created = now - timedelta(days=days_ago)

        issue = Issue(
            category=category,
            description=description,
            lat=lat,
            lng=lng,
            status=status,
            report_count=n_reports,
            upvotes=n_upvotes,
            near_sensitive=sensitive,
            department=department,
            created_at=created,
        )
        db.add(issue)
        db.flush()

        for i in range(n_reports):
            fake_phone_counter += 1
            db.add(Report(
                issue_id=issue.id,
                reporter_phone=f"90000{fake_phone_counter:05d}",
                note=description if i == 0 else "I am also facing this problem here.",
                created_at=created + timedelta(hours=i),
            ))
        for _ in range(n_upvotes):
            fake_phone_counter += 1
            db.add(Upvote(issue_id=issue.id, phone=f"90000{fake_phone_counter:05d}"))
        if status != "open":
            db.add(StatusLog(
                issue_id=issue.id,
                old_status="open",
                new_status=status,
                note="Sample data",
                changed_at=created + timedelta(hours=12),
            ))

        issue.priority_score = compute_priority(issue, now)

    db.commit()
    return {"seeded": True, "issues_added": len(SAMPLE_ISSUES)}

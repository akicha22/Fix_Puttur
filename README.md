# FixPuttur

**Report once. Count every voice. Fix by priority.**

A civic complaint platform for Puttur, Karnataka. Citizens report problems such as potholes, broken streetlights, water leaks and garbage with a photo and a map location. The backend merges duplicate reports into a single issue, ranks every issue by a transparent priority score, and gives authorities a department-wise queue of what to fix first.

> Built for **Byte Race 2026** (Project Sprint) at Vivekananda College of Engineering & Technology, Puttur, in association with the Department of Computer Science & Engineering.

---

## Live Demo and Links

| | Link |
|---|---|
| Live demo | [ADD LINK, or delete this row if there is none] |
| Demo video | [ADD LINK, or delete this row if there is none] |
| Slides | [ADD LINK, or delete this row if there is none] |

---

## 1. The Problem

Residents of Puttur report civic problems through phone calls, WhatsApp messages and in-person visits. This causes four problems:

- The **same issue is reported many times** in different places, so nobody sees its true scale.
- There is **no single view of what is most urgent**, so issues are handled by whoever complains loudest.
- Citizens **never find out what happened** to their complaint.
- Authorities **cannot prioritise what they cannot see.**

**Who is affected:** residents, daily commuters, students, and the officers who handle complaints.

**From our survey:** We asked [N] people in Puttur, and [X] did not know where to complain. *(Replace with your real numbers, or delete this paragraph if you did not run a survey.)*

---

## 2. The Solution

FixPuttur is one place to report a problem, with the sorting done by the backend instead of by people.

1. A citizen picks a category, drops a pin on the map, adds a photo and submits.
2. **Duplicate merging:** if an open issue of the same category already exists within **50 metres**, the new report is attached to it and its report count goes up. Otherwise a new issue is created.
3. **Priority scoring:** every issue gets a score so the most urgent rise to the top.
4. **Department routing:** each category goes to the right department's queue (Roads, Electricity, Water Supply, Sanitation, General).
5. **Status tracking:** officers update the status (open, in progress, resolved) and citizens see the change on the public board.
6. **Community voice:** other residents tap **"I'm affected too"** to add weight to an existing issue.

### Key features

- Duplicate detection by category and 50 m radius (haversine distance)
- Transparent, explainable priority score
- Public map and ranked issue board with status badges
- Department-wise authority dashboard with status updates and an audit log
- "I'm affected too" voting, limited to one vote per phone number per issue
- Escalation flag for issues left open too long

### How priority is calculated

```
priority = (report_count x 3) + (upvotes x 1) + (severity x 5) + (days_open x 2) + (10 if near a school or hospital)
```

| Category | Severity | Department |
|---|---|---|
| Open manhole | 10 | Roads |
| Water leak | 7 | Water Supply |
| Pothole | 6 | Roads |
| Streetlight | 4 | Electricity |
| Garbage | 3 | Sanitation |
| Request / suggestion | 2 | General |

Safety hazards are weighted above inconvenience. Time also counts, so an issue left open keeps climbing the list.

**Escalation:** an issue open for more than 3 days is flagged at level 1, and more than 7 days at level 2.

---

## 3. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Maps | Leaflet with OpenStreetMap tiles (free, no API key) |
| Backend | Python, FastAPI |
| Database | SQLite (via SQLAlchemy) |
| File storage | Local `uploads/` folder for photos |
| Server | Uvicorn |

**AI tools used:** Claude was used for code generation, debugging and drafting. All team members have reviewed the code and can explain how it works. *(Edit to match what you actually used.)*

---

## 4. Setup Steps

**Requirements:** Python 3.10 or newer, and Git.

### 1) Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/fixputtur.git
cd fixputtur
```

### 2) Create a virtual environment

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

Mac / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Run the app

```bash
uvicorn main:app --reload --host 0.0.0.0
```

### 5) Open it

- App: http://127.0.0.1:8000
- Interactive API docs: http://127.0.0.1:8000/docs

### 6) Load sample data (optional)

Open http://127.0.0.1:8000/docs, find `POST /seed` and click **Try it out → Execute**. This adds sample issues around Puttur so the map is not empty.

### Authority dashboard

The dashboard asks for a department PIN. The demo PIN is set in `main.py` ([ADD WHERE YOU SET IT]). This is for demonstration only. A real pilot would use proper authentication.

### Notes

- Browser location (the "use my location" button) works on `localhost` or HTTPS. On a phone over plain HTTP, tap the map to drop a pin instead.
- To open the app on a phone on the same Wi-Fi, use your laptop's local IP address and port 8000, for example `http://192.168.x.x:8000`.

---

## 5. API Overview

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/reports` | Submit a report (merges with a nearby open issue, or creates a new one) |
| GET | `/issues` | Public list sorted by priority, with optional filters |
| POST | `/issues/{id}/upvote` | "I'm affected too" |
| GET | `/dept/{name}/issues` | Ranked queue for one department |
| PATCH | `/issues/{id}/status` | Authority updates the status (PIN required, written to the status log) |
| GET | `/stats` | Totals for issues and reports |
| POST | `/seed` | Load sample data |

*(Edit this table to match the endpoints you actually built.)*

---

## 6. Project Structure

```
fixputtur/
  main.py            FastAPI app, database models, merge and priority logic
  index.html         Single-page frontend (Report, Public Board, Authority Dashboard)
  requirements.txt   Python dependencies
  uploads/           Uploaded photos (not committed)
  README.md
```

*(Edit this to match your actual folders and files.)*

---

## 7. Screenshots

| Report page | Public board | Authority dashboard |
|---|---|---|
| ![Report](screenshots/report.png) | ![Board](screenshots/board.png) | ![Dashboard](screenshots/dashboard.png) |

*(Create a `screenshots/` folder, add your 3 images with these names, or change the paths.)*

---

## 8. Current Status

Edit the ticks to match what really works today.

- [x] Problem research and database design
- [x] Complaint submission with category, location and photo
- [x] Duplicate merging (same category, within 50 m)
- [x] Priority score and ranked public board
- [ ] Authority dashboard with status updates
- [ ] "I'm affected too" voting
- [ ] Escalation flags
- [ ] Kannada interface and notifications

---

## 9. Challenges and How We Handle Them

| Challenge | Approach |
|---|---|
| Fake or spam reports | Photo encouraged, limits per phone number, issues reported by only one source are flagged |
| Privacy | Reporter phone numbers are never shown publicly |
| Adoption by authorities | A pilot with one department first. The ranked queue saves officers time. |

**Honest note:** FixPuttur has not yet been adopted by any local authority. The authority dashboard is a working demo of what a department officer or public representative's office would use, and a pilot with the local body is our proposed next step.

---

## 10. Future Scope

- Kannada interface and voice input
- WhatsApp / SMS status updates to citizens
- Ward-wise analytics and hotspot maps
- AI-assisted category suggestion from the uploaded photo
- Pilot with the local body and integration with their existing process

---

## 11. Team

**Team name:** [TEAM NAME]

| # | Name | USN | Branch / Year | Role |
|---|---|---|---|---|
| 1 | [Name] (Team Leader) | [USN] | [Branch, Year] | [Role] |
| 2 | [Name] | [USN] | [Branch, Year] | [Role] |
| 3 | [Name] | [USN] | [Branch, Year] | [Role] |
| 4 | [Name] | [USN] | [Branch, Year] | [Role] |

**Team leader contact:** [Phone] | [Email]

*(Delete unused rows.)*

---

## 12. Acknowledgements

Organised by Vivekananda College of Engineering & Technology, Nehru Nagar, Puttur, in association with the Department of Computer Science & Engineering and the Computer Science Engineering Students' Association (ACES).

Map data by [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.

# FixPuttur

**Thought, Built and Presented by AURA FARMERS**

A civic complaint platform for Puttur. Citizens report problems such as potholes, broken streetlights, water leaks, and garbage with a photo and a map location. The backend merges duplicate reports into a single issue, ranks every issue by a transparent priority score, and gives authorities a department-wise queue of what to fix first.

---

## Live Demo and Links

| | Link |
|---|---|
| Live demo | [fix-puttur.onrender.com](https://fix-puttur.onrender.com/) |

---

## 1. The Problem

Residents of Puttur report civic problems through phone calls, WhatsApp messages and in-person visits. This causes four problems:

- The **same issue is reported many times** in different places, so nobody sees its true scale.
- There is **no single view of what is most urgent**, so issues are handled by whoever complains loudest.
- Citizens **never find out what happened** to their complaint.
- Authorities **cannot prioritise what they cannot see.**

**Who is affected:** residents, daily commuters, students, and the officers who handle complaints.

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
| Hosting | Render |

**AI tools used:** Claude was used for code generation, debugging and drafting.
---

### Authority dashboard

The dashboard asks for a department PIN. The demo PIN is set in `main.py`. This is for demonstration only. A real pilot would use proper authentication.

---

## 4. Project Structure

```
fixputtur/
  main.py            FastAPI app, database models, merge and priority logic
  index.html         Single-page frontend (Report, Public Board, Authority Dashboard)
  requirements.txt   Python dependencies
  uploads/           Uploaded photos (not committed)
  README.md
```

---

## 5. Screenshots and Demo

Available within `demo/screenshots` folder

---

**Honest note:** FixPuttur has not yet been adopted by any local authority. The authority dashboard is a working demo of what a department officer or public representative's office would use, and a pilot with the local body is our proposed next step.

---

## 6. Future Scope

- Kannada interface and voice input
- WhatsApp / SMS status updates to citizens
- Ward-wise analytics and hotspot maps
- AI-assisted category suggestion from the uploaded photo
- Pilot with the local body and integration with their existing process

---

## 7. Team

**Team name:** AURA FARMERS

| # | Name | USN | Branch / Year | Role |
|---|---|---|---|---|
| 1 | Akshaya (Team Leader) | 1FYCV002 | [Civil Engineering, 1st Year] | Coder |
| 2 | P Shreenandama | 1FYME027 | [Mechanical Engineering, 2nd Year] | Motivator |

**Team leader contact:** +91 99008 50830 | unikaksince2008@gmail.com

---

## 8. Acknowledgements

Organised by Vivekananda College of Engineering & Technology, Nehru Nagar, Puttur, in association with the Department of Computer Science & Engineering and the Computer Science Engineering Students' Association (ACES).

Map data by [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.

# Build Readiness Document (BRD)

# ComplianceAI Lite

**Version:** 1.0

**Status:** Ready for Development

**Author:** Golu

**Last Updated:** 17 June 2026

---

# 1. Purpose

This document confirms that all functional, technical, and product requirements required to begin development of ComplianceAI Lite have been finalized.

The objective is to minimize uncertainty before implementation and provide a single source of truth for development.

---

# 2. Project Overview

ComplianceAI Lite automatically collects the latest RBI circulars, extracts text from PDF documents, summarizes them using Google Gemini, and displays concise compliance insights through a simple web application.

The MVP validates one core hypothesis:

> AI-generated summaries can significantly reduce the time compliance officers spend reading regulatory circulars.

---

# 3. Business Objective

Current Process

Compliance Officer

↓

Visit RBI Website

↓

Download PDF

↓

Read 20–50 pages

↓

Understand changes

↓

Determine required action

↓

Repeat daily

Estimated Time

30–90 minutes/day

---

Target Process

Compliance Officer

↓

Open ComplianceAI

↓

View summarized circulars

↓

Read action items

↓

Open original PDF if required

Estimated Time

Less than 2 minutes

---

# 4. Success Metrics

The MVP is successful when:

* Latest RBI circulars are displayed automatically.
* AI summary is generated successfully.
* Action items are clearly visible.
* Users can open the original RBI PDF.
* Complete workflow functions without manual intervention.

---

# 5. Scope

## Included

* RBI Circular Scraper
* PDF Downloader
* PDF Text Extraction
* Gemini AI Integration
* Summary Generation
* Web UI
* Responsive Design
* Render Deployment

---

## Excluded

* Authentication
* User Accounts
* MongoDB
* Email Digest
* Search
* Filters
* Notifications
* Payments
* Admin Panel
* SEBI Support
* IRDAI Support

---

# 6. User Persona

Primary User

Compliance Officer

Organization

NBFC

Payment Company

Digital Lender

Goals

* Save time
* Never miss a circular
* Understand regulations quickly

Pain Points

* Manual monitoring
* Long PDFs
* Multiple regulator websites
* No centralized feed

---

# 7. Functional Readiness Checklist

| Requirement                    | Status |
| ------------------------------ | ------ |
| PRD Approved                   | ✅      |
| MVP Scope Defined              | ✅      |
| Feature Specification Complete | ✅      |
| User Flow Defined              | ✅      |
| Success Criteria Defined       | ✅      |
| Out of Scope Defined           | ✅      |

---

# 8. Technical Stack

Backend

FastAPI

Language

Python 3.12

Frontend

Jinja2

TailwindCSS

Libraries

requests

beautifulsoup4

pdfplumber

google-generativeai

uvicorn

Deployment

Render

Version Control

GitHub

---

# 9. External Dependencies

| Dependency          | Purpose             |
| ------------------- | ------------------- |
| RBI Website         | Source of circulars |
| Google Gemini API   | AI summaries        |
| Internet Connection | Data retrieval      |
| Render              | Deployment          |
| GitHub              | Source control      |

---

# 10. Folder Structure

compliance-ai-lite/

app.py

scraper.py

pdf_parser.py

summarizer.py

config.py

requirements.txt

.env

README.md

templates/

index.html

static/

assets/

---

# 11. Environment Variables

GOOGLE_API_KEY

SECRET_KEY

APP_ENV

PORT

---

# 12. Development Milestones

Phase 1

Project Setup

Estimated Time

30 minutes

Deliverable

Running FastAPI application

---

Phase 2

RBI Scraper

Estimated Time

2 hours

Deliverable

Latest circular metadata

---

Phase 3

PDF Downloader

Estimated Time

1 hour

Deliverable

Downloaded PDFs

---

Phase 4

PDF Parser

Estimated Time

2 hours

Deliverable

Extracted text

---

Phase 5

Gemini Integration

Estimated Time

2 hours

Deliverable

JSON summary

---

Phase 6

Frontend

Estimated Time

3 hours

Deliverable

Summary cards

---

Phase 7

Deployment

Estimated Time

2 hours

Deliverable

Live application

---

# 13. Acceptance Criteria

Development is considered complete when:

* Application starts without errors.
* Latest five RBI circulars load successfully.
* PDFs download successfully.
* Text extraction succeeds.
* Gemini generates structured JSON.
* Circular cards render correctly.
* Original PDF link opens.
* Application is accessible via a public URL.

---

# 14. Risks

| Risk                          | Mitigation                         |
| ----------------------------- | ---------------------------------- |
| RBI website structure changes | Keep scraper modular               |
| PDF extraction fails          | Skip invalid PDF and continue      |
| Gemini timeout                | Display error message and continue |
| Slow network                  | Retry request with timeout         |
| Invalid API key               | Validate during startup            |

---

# 15. Assumptions

* RBI website remains publicly accessible.
* Gemini API quota is available.
* Internet connection is stable.
* PDFs contain readable text.
* Render free tier is sufficient for MVP.

---

# 16. Non-Functional Requirements

Performance

* Homepage loads within 5 seconds.
* Summary generation within 15 seconds.

Reliability

* Application does not crash if one circular fails.
* Errors are logged.

Security

* API keys stored in environment variables.
* HTTPS deployment.

Usability

* Mobile responsive.
* Simple navigation.
* Clean typography.

---

# 17. Testing Checklist

## Scraper

* Fetches latest five circulars.
* Correct title extracted.
* Correct PDF URL extracted.

## PDF Parser

* PDF downloads.
* Text extracted.
* Empty PDFs handled.

## AI

* JSON returned.
* Summary generated.
* Action items generated.

## Frontend

* Cards render correctly.
* Mobile responsive.
* Links open correctly.

## Deployment

* Application accessible publicly.
* No environment variable errors.

---

# 18. Deliverables

* GitHub Repository
* Live Render URL
* README.md
* MVP.md
* PRD
* FRS
* Build Readiness Document
* Architecture Diagram
* Screenshots

---

# 19. Build Readiness Status

| Area                    | Status  |
| ----------------------- | ------- |
| Product Requirements    | ✅ Ready |
| Functional Requirements | ✅ Ready |
| Technical Stack         | ✅ Ready |
| Architecture            | ✅ Ready |
| Development Plan        | ✅ Ready |
| Dependencies            | ✅ Ready |
| Risks Identified        | ✅ Ready |
| Success Metrics         | ✅ Ready |

---

# Final Decision

**Build Status:** 🟢 READY TO START DEVELOPMENT

No blockers remain.

Development can begin immediately.

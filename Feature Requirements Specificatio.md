# Feature Requirements Specification (FRS)

# Project

ComplianceAI Lite

Version: 1.0

Status: MVP

---

# Overview

ComplianceAI Lite automatically monitors RBI circulars, extracts their contents, summarizes them using Gemini AI, and presents concise compliance insights on a simple web application.

The MVP focuses on validating whether AI-generated summaries reduce the time compliance officers spend reading regulatory circulars.

---

# Feature List

| ID | Feature | Priority |
|----|----------|----------|
| F-01 | Fetch Latest RBI Circulars | High |
| F-02 | Download Circular PDF | High |
| F-03 | Extract PDF Text | High |
| F-04 | AI Summary Generation | High |
| F-05 | Display Circular Cards | High |
| F-06 | View Original PDF | Medium |
| F-07 | Manual Refresh | Medium |
| F-08 | Error Handling | High |

---

# F-01 Fetch Latest RBI Circulars

## Description

The system shall automatically fetch the latest circulars published on the RBI website.

---

## User Story

As a Compliance Officer

I want

the latest RBI circulars

so that

I don't have to manually visit RBI's website.

---

## Functional Requirements

The system shall

• Connect to RBI Circular page

• Parse latest circular entries

• Extract

- Title

- Publish Date

- PDF Link

• Return latest five circulars

---

## Acceptance Criteria

✓ Latest 5 circulars displayed

✓ Correct title

✓ Correct date

✓ Valid PDF URL

---

# F-02 Download Circular PDF

## Description

The system shall download the PDF associated with each circular.

---

## User Story

As a user

I want

the system to automatically fetch PDFs

so that

I never manually download them.

---

## Functional Requirements

System shall

Download PDF

Verify successful download

Reject invalid links

Continue processing remaining files

---

## Acceptance Criteria

✓ PDF downloaded successfully

✓ Failed downloads logged

✓ Application does not crash

---

# F-03 Extract PDF Text

## Description

Extract readable text from RBI PDFs.

---

## User Story

As a user

I want

the PDF converted into text

so AI can summarize it.

---

## Functional Requirements

System shall

Open PDF

Extract all readable text

Ignore images

Remove unnecessary whitespace

Return plain text

---

## Acceptance Criteria

✓ Extracted text not empty

✓ At least 80% readable

✓ Processing under 5 seconds

---

# F-04 AI Summary Generation

## Description

Generate compliance-friendly summaries using Gemini.

---

## User Story

As a compliance officer

I want

a concise explanation

so I immediately understand the regulation.

---

## Functional Requirements

System shall send extracted text to Gemini.

Gemini must return

Summary

Affected Organizations

Severity

Action Items

Compliance Deadline

---

## Output Format

{
"title": "",
"summary": "",
"affected": "",
"severity": "",
"action_items": [],
"deadline": ""
}

---

## Acceptance Criteria

✓ JSON returned

✓ Summary under 200 words

✓ Action items generated

✓ Severity assigned

---

# F-05 Display Circular Cards

## Description

Display every summarized circular as a clean information card.

---

## Card Layout

--------------------------------

Title

Published Date

Summary

Affected Organizations

Severity Badge

Action Items

Read Original PDF

--------------------------------

---

## Functional Requirements

System shall display

Title

Summary

Date

Severity

Affected Users

Action Items

PDF Link

---

## Acceptance Criteria

✓ Cards render correctly

✓ Mobile responsive

✓ Information readable

---

# F-06 View Original PDF

## Description

Allow users to open the official RBI document.

---

## Functional Requirements

Every card shall contain

Read Original PDF

Clicking opens RBI PDF in new tab.

---

## Acceptance Criteria

✓ Opens correct PDF

✓ Original RBI website

---

# F-07 Manual Refresh

## Description

Allow users to refresh the latest circulars.

---

## Functional Requirements

Refresh button

↓

Run scraper

↓

Generate summaries

↓

Reload page

---

## Acceptance Criteria

✓ Refresh completes

✓ Updated circulars visible

---

# F-08 Error Handling

## Description

Gracefully handle failures.

---

## Possible Errors

RBI unavailable

Internet unavailable

PDF download failed

Gemini timeout

Empty response

---

## System Behaviour

Show friendly message

Continue processing remaining circulars

Log error

Never crash application

---

# User Interface Requirements

Homepage

Navigation

Logo

Refresh Button

Latest RBI Circulars

Footer

---

# Circular Card

Title

Date

Summary

Severity Badge

Affected Organizations

Action Items

Read Original PDF

---

# Non-functional Requirements

Performance

Homepage loads within

5 seconds

Summary generation

15 seconds

Maximum

---

Reliability

Application uptime

99%

No duplicate cards

Graceful error handling

---

Security

Read-only system

No authentication

No user data stored

HTTPS deployment

---

Usability

Responsive layout

Desktop

Tablet

Mobile

Readable typography

Simple navigation

---

Browser Support

Chrome

Edge

Firefox

Safari

Latest versions

---

Dependencies

Python

FastAPI

BeautifulSoup

Requests

pdfplumber

Gemini API

Jinja2

TailwindCSS

---

Out of Scope

Authentication

Database

Email Digests

Notifications

User Accounts

Payment

Subscriptions

Search

Filters

Analytics

Admin Dashboard

SEBI

IRDAI

Slack Integration

Audit Reports

---

Success Criteria

The MVP is considered complete if

✓ Latest RBI circulars are fetched

✓ PDFs download successfully

✓ Text extracted successfully

✓ Gemini generates structured summaries

✓ Summaries displayed on webpage

✓ Original PDFs accessible

✓ Application deployed publicly

---

Future Features

Version 2

MongoDB

Historical Circulars

Email Digest

Daily Scheduler

Search

Filters

Authentication

Version 3

SEBI Integration

IRDAI Integration

Slack Notifications

Role-based Filtering

Version 4

Compliance Timeline

Audit Reports

JIRA Integration

Risk Analytics

AI Chat Assistant




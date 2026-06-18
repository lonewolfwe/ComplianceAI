# ComplianceAI Lite
## MVP Specification

Version: 1.0

---

# Overview

ComplianceAI Lite is an AI-powered regulatory monitoring tool for Indian fintech companies.

Instead of manually reading RBI circulars every morning, users open one webpage and instantly see AI-generated summaries of the latest circulars.

This MVP validates one assumption:

> AI summaries are valuable enough to replace manual reading.

No authentication.

No subscriptions.

No email.

No payments.

No dashboard analytics.

Just solve one problem extremely well.

---

# Problem Statement

Compliance officers spend 30–90 minutes every day checking:

- RBI
- SEBI
- IRDAI

websites.

Each regulator publishes updates independently.

Users must:

- Open website
- Find latest circular
- Download PDF
- Read 20–50 pages
- Understand impact
- Decide whether action is needed

The process is repetitive.

---

# Goal

Reduce

90 minutes

↓

2 minutes

using AI summaries.

---

# Users

Primary Users

• Compliance Officer

• Risk Manager

• Legal Team

• Founder of regulated fintech startup

---

# User Flow

User opens website

↓

Homepage loads

↓

Backend fetches latest RBI circulars

↓

Downloads PDF

↓

Extracts text

↓

Gemini summarizes

↓

Frontend displays summaries

Done.

---

# MVP Scope

Included

✅ RBI scraper

✅ Download PDF

✅ Extract text

✅ AI summary

✅ Display latest circulars

Not Included

❌ Login

❌ Signup

❌ Database

❌ Email

❌ Notifications

❌ Payment

❌ User profiles

❌ Admin panel

❌ Search

❌ Filters

❌ Mobile app

❌ Multi-user

---

# Features

## Feature 1

Latest RBI Circulars

Description

Fetch latest 5 circulars.

Display

- Title

- Date

- Link

---

## Feature 2

PDF Extraction

Automatically

Download PDF

↓

Extract text

↓

Store temporarily in memory

No database.

---

## Feature 3

AI Summary

Gemini receives extracted text.

Returns

Summary

Who is affected

Risk Level

Required Action

Deadline

---

Expected JSON

{
"title":"",
"summary":"",
"affected":"",
"action_items":"",
"severity":"",
"deadline":""
}

---

# Feature 4

Simple Web Interface

Cards

-------------------------

RBI Circular

Date

Summary

Severity

Who is affected

Action Items

Read Original PDF

-------------------------

---

# UI

Home

-----------------------------------

ComplianceAI Lite

Latest RBI Circulars

-----------------------------------

CARD

Title

Date

Summary

Affected

Severity

Action

Read Original PDF

-----------------------------------

CARD

-----------------------------------

CARD

-----------------------------------

---

# Tech Stack

Backend

FastAPI

Frontend

Jinja2

Tailwind CSS

Language

Python

Libraries

requests

BeautifulSoup4

pdfplumber

google-generativeai

FastAPI

Jinja2

uvicorn

Environment

Python 3.12

Hosting

Render

Repository

GitHub

---

# Folder Structure

compliance-ai-lite/

app.py

scraper.py

pdf_parser.py

summarizer.py

templates/

index.html

static/

requirements.txt

README.md

.env

---

# API

GET /

Returns webpage.

---

GET /api/circulars

Returns JSON

[
{
"title":"",
"date":"",
"summary":"",
"severity":"",
"affected":"",
"action_items":"",
"pdf_url":""
}
]

---

# AI Prompt

You are an Indian fintech compliance analyst.

Read the RBI circular.

Return:

1 Summary

2 Who is affected

3 Risk Level

4 Required action

5 Compliance deadline

Respond ONLY in JSON.

---

# Non Functional Requirements

Page load

<5 seconds

Summary generation

<15 seconds

Responsive

Desktop

Tablet

Mobile

---

# Success Criteria

The MVP is complete if:

✔ Fetches latest RBI circulars

✔ Downloads PDF

✔ Extracts text

✔ Generates AI summary

✔ Displays on webpage

✔ Deploys on Render

---

# Future Versions

V2

Database

Historical circulars

Search

Filters

Authentication

Email digest

---

V3

SEBI

IRDAI

Daily cron

Slack

Teams

WhatsApp

---

V4

Personalized alerts

Role-based filtering

Compliance tracking

Audit reports

JIRA integration

---

# Out of Scope

Analytics

Billing

Subscription

Admin dashboard

Organization management

Vector database

RAG

Fine-tuning

Multi-agent workflows

These features do not help validate the core hypothesis and will not be built in the MVP.

---

# Deliverables

Live URL

GitHub Repository

README

Working Demo

Architecture Diagram

Screenshots

Deployment on Render

---

# Timeline

Day 1

Project setup

RBI scraper

PDF extraction

Gemini integration

Day 2

FastAPI

Frontend

Deployment

README

Portfolio screenshots

Project complete.
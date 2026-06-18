# 00-Development-Rules.md

# ComplianceAI Lite

## Development Rules & Engineering Standards

**Version:** 1.0

**Status:** Active

---

# Purpose

This document defines the engineering standards that must be followed throughout the development of ComplianceAI Lite.

Every development task must comply with these rules.

If any rule conflicts with generated code, these rules take precedence.

---

# Primary Goal

Build a clean, maintainable, production-ready MVP that demonstrates software engineering best practices.

Priorities:

1. Correctness
2. Simplicity
3. Readability
4. Maintainability
5. Performance

Never sacrifice readability for clever code.

---

# Engineering Principles

The project must follow:

* SOLID Principles
* DRY (Don't Repeat Yourself)
* KISS (Keep It Simple)
* YAGNI (You Aren't Gonna Need It)
* Separation of Concerns
* Single Responsibility Principle
* Composition over Inheritance

---

# Architecture Rules

Use a modular architecture.

Business logic must never exist inside routes.

Routes should only:

* Receive request
* Validate request
* Call service
* Return response

Example:

```
Route

↓

Service

↓

Utility

↓

External API
```

Never place scraping logic inside FastAPI endpoints.

---

# Project Structure

```
compliance-ai-lite/

app.py

config.py

requirements.txt

.env.example

README.md

src/

    routes/

    services/

    scraper/

    ai/

    parsers/

    utils/

    models/

    schemas/

templates/

static/

tests/

docs/
```

Every folder must have one clear responsibility.

---

# Naming Conventions

Files

snake_case.py

Classes

PascalCase

Functions

snake_case()

Variables

snake_case

Constants

UPPER_CASE

Private methods

_prefix()

---

# Code Style

Follow PEP 8.

Maximum line length

100 characters

Use meaningful variable names.

Avoid abbreviations.

Good

```
latest_circulars
```

Bad

```
lst
```

---

# Function Rules

Each function should:

* Perform one task only.
* Be easy to understand.
* Return predictable output.

Preferred length

<30 lines

Maximum

50 lines

Split large functions into smaller helpers.

---

# Class Rules

Classes should represent one concept.

Avoid "God Classes."

Prefer dependency injection.

Avoid static utility classes unless justified.

---

# Type Hints

All public functions require type hints.

Example

```python
def summarize_pdf(text: str) -> Summary:
    ...
```

Avoid using `Any` unless absolutely necessary.

---

# Documentation

Every public function requires a docstring.

Example

```python
"""
Extract text from a PDF document.

Args:
    pdf_path: Path to PDF.

Returns:
    Extracted text.
"""
```

Complex logic must include concise explanatory comments.

Do not comment obvious code.

---

# Error Handling

Never ignore exceptions.

Never use

```python
except:
```

Always catch specific exceptions.

Log every unexpected error.

Return user-friendly messages.

Never expose stack traces.

---

# Logging

Use Python logging.

Do not use

```python
print()
```

Log levels

DEBUG

INFO

WARNING

ERROR

CRITICAL

Every external API request should be logged.

---

# Environment Variables

Never hardcode:

* API Keys
* URLs
* Secrets
* Tokens
* Passwords

Everything sensitive must come from `.env`.

Provide an `.env.example`.

---

# Security Rules

Never commit secrets.

Validate all user input.

Escape HTML output.

Sanitize external data.

Never trust third-party APIs.

---

# AI Integration Rules

Gemini responses must always be validated.

Expected output format:

```
JSON
```

If invalid:

Retry once.

If still invalid:

Return graceful error.

Never assume AI output is correct.

---

# Scraper Rules

Use timeouts.

Retry failed requests.

Respect robots.txt where applicable.

Use descriptive User-Agent.

Handle website structure changes gracefully.

Do not crash if one circular fails.

---

# API Rules

Use REST conventions.

Return proper HTTP status codes.

Validate every request.

Use Pydantic models.

Document every endpoint.

Never return raw exceptions.

---

# Frontend Rules

Use:

* Jinja2
* Tailwind CSS

Avoid unnecessary JavaScript.

Mobile-first design.

Accessibility:

* Semantic HTML
* Proper heading hierarchy
* Keyboard-friendly navigation
* Sufficient color contrast

---

# Dependency Rules

Add only required packages.

Avoid unnecessary frameworks.

Prefer standard library when possible.

Review new dependencies before adding them.

---

# Git Workflow

Commit after every completed feature.

Commit message format

```
feat:

fix:

refactor:

docs:

test:

chore:
```

Never mix multiple features in one commit.

---

# Testing Rules

Every core module should be testable.

Target

80% coverage

Use pytest.

Mock:

* Gemini API
* Network Requests

Tests should not require internet.

---

# Performance Rules

Homepage

<5 seconds

AI summary

<15 seconds

Avoid duplicate API requests.

Avoid unnecessary loops.

---

# Code Review Checklist

Before marking any task complete:

* Code runs successfully.
* No unused imports.
* No duplicate code.
* No hardcoded values.
* Type hints complete.
* Docstrings complete.
* Logging added.
* Errors handled.
* Functions small.
* Naming clear.

---

# Documentation Rules

Whenever architecture changes:

Update:

* README
* MVP
* FRS
* Architecture
* API Specification

Documentation must stay synchronized with the implementation.

---

# Definition of Done

A feature is complete only when:

* Requirements implemented.
* Code reviewed.
* Linting passes.
* Tests pass.
* Documentation updated.
* No known critical bugs.
* Git committed.

---

# Things We Will NOT Do

* Premature optimization
* Overengineering
* Unused abstractions
* Dead code
* Large utility files
* Massive functions
* Hidden business logic
* Duplicate implementations
* Hardcoded secrets

---

# AI Development Instructions

When generating code:

* Think before coding.
* Prefer simple solutions.
* Produce production-quality code.
* Follow existing architecture.
* Reuse existing modules.
* Avoid unnecessary dependencies.
* Keep code readable.
* Explain major design decisions.
* Do not invent requirements.
* Ask for clarification if requirements conflict.

---

# Development Philosophy

Build the smallest solution that completely solves the current problem.

Every new feature must answer:

1. Does this solve a real user problem?
2. Is it required for the MVP?
3. Can it be implemented more simply?
4. Is it maintainable?
5. Does it improve the overall product?

If the answer is **No**, do not implement it.

---

# Final Rule

Every development session begins by reading:

1. 00-Development-Rules.md
2. PRD.md
3. MVP.md
4. Feature-Requirements-Specification.md
5. Build-Readiness-Document.md

No code should be written until all five documents have been reviewed and understood.

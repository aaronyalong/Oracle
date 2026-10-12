---
tags: [projects]
---
# Study Planner

A web app for planning study sessions and tracking coursework deadlines.

## Stack
- Backend: Scala 3 with [[ZIO]], built with [[sbt]].
- Database: [[PostgreSQL]]. We moved off the original database after the [[2026-09-20]] meeting.
- Task search uses the database's built-in full-text search (see [[Full-Text Search]]).

## Status
Deadlines and reminders work; calendar sync is next.

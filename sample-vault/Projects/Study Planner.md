---
tags: [projects]
---
# Study Planner

A web app for planning study sessions and tracking coursework deadlines.

## Stack
- Backend: Scala 3 with [[ZIO]], built with [[sbt]].
- Database: [[PostgreSQL]]. We moved off the original database after the [[2026-09-20]] meeting.
- Task search uses the database's built-in full-text search (see [[Full-Text Search]]).

## Reminders — first plan (superseded)
A cron job every 15 minutes would email each user their upcoming deadlines. Dropped: the emails landed in spam folders and 15 minutes was too coarse for short study blocks.

## Reminders — current
Reminders are browser push notifications, scheduled per user with ZIO's `Schedule` so each one fires at the exact time.

## Status
Deadlines and reminders work; calendar sync is next.

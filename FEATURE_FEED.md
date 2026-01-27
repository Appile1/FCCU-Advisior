# Feature: Live Course Updates Feed
**Date:** Jan 27, 2026
**Branch:** `feature/course-feed`

## Overview
This feature adds a "Live Updates" feed to the application, allowing students to see real-time changes in course availability, new sections, instructor assignments, and schedule changes.

## Changes

### 1. `feed_generator.py` (New Script)
- **Purpose**: Compares course data between scrapes to identify changes.
- **Location**: Root directory.
- **Key Logic**:
    - Loads current course data (`course_data/{term}_courses.json`).
    - Loads previous state (`course_data/previous_state.json`).
    - Diffs the two states to find:
        - **Seats Available**: When seats go from 0 (or "Closed") to > 0.
        - **New Section**: When a section ID appears that wasn't there before.
        - **Instructor Change**: When the instructor field changes.
        - **Schedule Change**: When the schedule string changes.
    - Appends events to `course_data/feed_events.json`.
    - Automatically copies `feed_events.json` to the frontend's `public` folder (if found at `../fccuadvisiorfronetend/public`) for local dev convenience.
- **Usage**: Run `python feed_generator.py` immediately after running the main `bas4.py` scraper.

## Integration Instructions
1.  **Deployment**: Ensure `feed_generator.py` is executed in your scraping pipeline (e.g., GitHub Actions or Cron job) *after* the main scraper.
2.  **Dependencies**: Uses standard libraries (`json`, `os`, `datetime`, `shutil`). No new pip packages required.

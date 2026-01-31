# DW3 Survey Logger v0.9.9

## Project Status

**This is still under active development.**  
It was created in 8 days to support **DW3 expeditions**.

https://forums.frontier.co.uk/threads/dw3-distant-worlds-3-science-thread.643734/

Because development is ongoing and iterative, **bugs and rough edges should be expected**. The focus so far has been functionality and data integrity rather than polish.

## Known Issues (v0.9.9)

The following issues are **known and confirmed** in version **0.9.8**.  
They do **not affect collected data integrity**, but may impact usability.


- **Observation window is too large**  
  The observation panel can exceed practical screen space on smaller displays.

- **Excel export folder cannot be changed**  
  The export location is currently fixed and ignores user selection.

  These issues will be addressed as part of upcoming updates.

---

## Overview

DW3 Survey Logger is for commanders participating in **DW3 (Deep Space Waypoint 3)**.  
It helps collect, structure, validate and export survey data from *Elite Dangerous* in a consistent way.

The logger combines:
- Automatic journal parsing from the game
- Human observations entered during flight
- Structured storage in a local SQLite database

The result is **clean, comparable data** that DW3 teams can use without manual cleanup.

---

## Application Layout & Sections

Below is an overview of the main sections of the application and how they work together.  
Each section will soon have screenshots to help new users orient themselves.



---

### 1. Main Observation Screen

![Main Observation Screen](`assets/main_observation_screen.png`)

This is the primary workspace during flight.

Here you:
- See current system information
- Monitor sampling progress
- Enter observation values
- Complete samples when finished


---

### 2. Session & Sample Tracking

![Session Sample Tracking](`assets/session_sample_tracking.png`)

Each expedition run is organized into:
- **Sessions** (a continuous exploration period)
- **Samples** (individual measurement sets)

The logger automatically keeps track of:
- Z-bins
- Sample numbers
- Completion state

This ensures consistency across commanders and across time.

---

### 3. Journal Monitoring

![Journal Monitor](`assets/journal_monitor.png`)

The application continuously watches your **Elite Dangerous journal folder**.

It:
- Detects new journal entries in real time
- Parses only relevant events
- Ignores unrelated noise

No data is uploaded or shared automatically. Everything remains local on your machine.

---

### 4. Drift Guardrail

![Drift Guardrail](`assets/drift_guardrail.png`)

Drift Guardrail helps detect unintended movement during measurements.

It:
- Tracks positional drift during sampling
- Flags samples that may be compromised
- Assists in deciding whether a re-sample is needed

This improves scientific reliability without enforcing hard rules.

---

### 5. ELW Scans & Activity Tier (Informational)

![Elw Activity Tier](`assets/elw_activity_tier.png`)

When scanning **Earth-Like Worlds (ELWs)**, the application displays a small activity tier indicator.

#### What the ELW Activity Tier Is

- A **local, personal indicator** based on your own ELW scan activity
- Designed purely for engagement and feedback


#### What the ELW Activity Tier Is *Not*

- Not a competition
- Not a ranking between commanders
- Not included in exported DW3 data

The activity tier has **zero impact** on:
- Data quality
- Validation
- DW3 worksheet exports
- Scientific usefulness

Two commanders with different ELW activity tiers can produce **equally valid data**.

#### Why It Exists
 
The ELW activity tier exists to add a light sense of progression **without turning science into competition**.

If it ever becomes distracting or controversial, it may be:
- Reworked
- Made optional
- Removed entirely

Community feedback will guide that decision.

---

### 6. Data Storage (SQLite)

Screenshot: `assets/database_overview.png`

All collected data is stored locally in a **SQLite database**.

Advantages:
- Fast and reliable
- Easy to back up
- No external services required
- Clear structure for later analysis

Both raw and processed values are preserved.

---

### 7. Export to DW3 Worksheets

Screenshot: `assets/excel_export.png`

Completed samples can be exported to **DW3-compatible Excel worksheets**.

Exports include:
- Commander name
- Session and sample identifiers
- Measurement values
- Required metadata for DW3 analysis

Files are named clearly so coordinators can identify them without opening the file.

---

### 8. Options & Configuration

Screenshot: `assets/options_screen.png`

The options screen allows you to:
- Select journal and output folders
- Adjust hotkeys


Most settings persist across restarts.

---

## Ranking, Scoring & Intent

### This Is Not a Competitive Tool

DW3 Survey Logger is **not designed to rank commanders against each other**.

No commander is judged, compared or evaluated based on performance.

### Summary

- The app focuses on **data collection**
- It is **not a leaderboard**
- ELW activity tiers are local and purely for fun

---

## Installation

### Windows (Recommended)
1. Download the latest EXE from GitHub Releases
2. Run the application
3. Select your Elite Dangerous journal folder on first launch

### Linux / Advanced Users
```bash
pip install -r requirements.txt
python main.py
```

---

## Current Limitations

- UI is "functional" but not final
- Some validation is still evolving

These limitations are expected at this stage of development.

---

## Roadmap

### Next Focus
- **Data validation**
  - Prevent incomplete or invalid samples
  - Stronger consistency checks before export

- **UI improvements**
  - Clearer feedback
  - Improved layout and readability

### Future Ideas
- Session summaries and statistics
- Improved drift diagnostics
- Guided workflows for new commanders

---

## Versioning Note

Recent releases focused primarily on internal stability and correctness.  
Version numbering will stabilize once core behavior is fully locked in.

---

## Disclaimer

This project is **not officially affiliated with Frontier Developments or DW3 leadership**.  
It is a community-built tool provided as-is.

---

## Feedback & Contributions

Bug reports and suggestions are welcome via GitHub Issues or Discord.  
Please include logs and steps to reproduce where possible.

---

## Acknowledgements

- CMDRs testing early builds 
- The DW3 expedition community
- Stellar Density Scan Worksheet created by CMDR Satsuma
- Distant Radio 33.05
- Frontier Development
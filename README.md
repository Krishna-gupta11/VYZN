# VYZN — Personal Productivity Hub

**Build discipline. Track progress. Become your next version.**

VYZN is a local-first Windows desktop productivity application built with Python, PySide6, and SQLite. It combines habit tracking, task management, personal notes, journaling, calendar planning, and progress analytics in a dark, gaming-inspired interface.

Designed around consistency and personal growth, VYZN adds a gamified progression system with XP, ranks, achievements, and activity tracking to make everyday productivity more engaging.

**Current Version:** `v1.0.0`  
**Platform:** Windows 10/11  
**Application Type:** Desktop  
**Data Storage:** Local SQLite database

---

## Table of Contents

- [Download VYZN](#-download-vyzn)
- [Features](#-features)
- [Screenshots](#-screenshots)
- [Project Structure](#-project-structure)
- [Technology Stack](#-technology-stack)
- [Run the Application](#-run-the-application)
- [Build the Windows Executable](#-build-the-windows-executable)
- [How Data Storage Works](#-how-data-storage-works)
- [Development Guide](#-development-guide)
- [Privacy](#-privacy)
- [Known Limitations](#-known-limitations)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 📥 Download VYZN

You can use VYZN without setting up a Python development environment.

### Option 1 — Download the Windows application

**Recommended for regular users.**

Visit the [VYZN Releases page](https://github.com/Krishna-gupta11/VYZN/releases/latest) and download `VYZN_SHARE.zip` from the latest release.

**Getting started:**

1. Download `VYZN_SHARE.zip`.
2. Extract the entire ZIP archive to a folder on your computer.
3. Open the extracted folder.
4. Double-click `VYZN.exe`.
5. Start creating habits, managing tasks, and tracking your progress.

The packaged application includes the required runtime files. You do not need to install Python separately.

**Important:** Keep the extracted application files together. Do not move only `VYZN.exe` out of its folder, because the packaged application depends on its accompanying files.

### Option 2 — Explore the source code

**Recommended for developers, students, and contributors.**

Browse the source code directly in this repository or clone it to your computer.

The source version allows you to inspect the implementation, modify the interface, add features, run tests, and build your own Windows executable.

---

## ✨ Features

### Habit Tracking
- Create and manage daily habits.
- Track habit completion and consistency.
- Monitor streaks and accumulated progress.
- Archive habits when they are no longer active.

### Task Management
- Create, edit, and organize tasks.
- Assign Low, Medium, or High priority.
- Set optional deadlines.
- Add descriptions and additional task details.
- Identify overdue tasks.
- Track task completion.

### Calendar and Important Dates
- Navigate between calendar months.
- Jump directly to the current date.
- View activity markers and task deadlines.
- Add personal events and important dates.
- Categorize events and attach optional notes.
- Configure yearly recurring dates for occasions such as birthdays and anniversaries.
- Select a date to inspect its associated activity and scheduled tasks.

### Notes and Journal
- Maintain personal notes.
- Write journal entries and daily reflections.
- Keep personal information organized within the application.

### Progress and Gamification
- Earn XP through supported activities.
- Track levels, ranks, and achievements.
- Monitor current and best habit streaks.
- Review habit completions, completed tasks, and journal activity.
- View activity charts covering the last 7 and 30 days.

### Personal Profile
- Customize your display name.
- Add a motivational tagline to the dashboard.
- Manage important dates.
- Reset personal data when you want to start fresh.

### Appearance and Interface
- Dark, gaming-inspired interface.
- Custom VYZN application icon.
- Color theme customization.
- Native Qt-drawn activity charts.

### Data Management
- Local SQLite database.
- Automatic database schema migrations for supported existing databases.
- Timestamped database backups before the Clear All Data operation.
- Separate application data for each Windows user in the packaged version.

---

## 🖥️ Screenshots

Screenshots of the actual application can be added here to demonstrate the interface.

Suggested screenshots:

| Screenshot | What it demonstrates |
|---|---|
| Dashboard | Profile greeting, motivational tagline, and productivity overview |
| Habits | Daily habit tracking and consistency |
| Tasks | Priorities, deadlines, and task management |
| Calendar | Activity markers, deadlines, and important dates |
| Analysis | Activity charts, streaks, and progress metrics |
| Profile | Personalization and important date management |

To add screenshots, create a `docs/screenshots/` directory and place your images inside it. Then embed them in this README, for example:

```markdown
![VYZN Dashboard](docs/screenshots/dashboard.png)
```

Use screenshots captured from the actual VYZN application.

---

## 📂 Project Structure

The repository is organized to support running, testing, and packaging the application.

```text
VYZN/
├── assets/
│   └── icons/
│       ├── VYZN.ico
│       └── VYZN.png
│
├── src/
│   └── vyzn/
│       ├── __init__.py
│       └── main.py
│
├── tests/
│   └── test_store.py
│
├── .gitignore
├── BUILD_EXECUTABLE.txt
├── README.md
├── build_windows.bat
└── requirements.txt
```

### What each part contains

- **`src/vyzn/`** — Main application source code and application entry point.
- **`assets/icons/`** — Application icons used for branding and Windows packaging.
- **`tests/`** — Automated tests for supported application functionality.
- **`requirements.txt`** — Python dependencies.
- **`build_windows.bat`** — Windows build script for packaging the application.
- **`BUILD_EXECUTABLE.txt`** — Additional instructions for building the executable.
- **`.gitignore`** — Excludes development artifacts and local data from Git tracking.

The current implementation keeps most application logic in `src/vyzn/main.py` to preserve the customized interface while the project evolves.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic |
| PySide6 / Qt | Desktop interface and widgets |
| SQLite | Local database and persistent storage |
| PyInstaller | Packaging the Windows application |
| Git and GitHub | Version control and source distribution |
| Python `unittest`-compatible testing tools | Automated tests, depending on the test setup |

The application does not require a remote database server for its normal local operation.

---

## 🚀 Run the Application

These instructions are for developers running VYZN from its source code on Windows 10 or Windows 11.

### Prerequisites

- Python 3.11 or later recommended.
- Git, if cloning the repository.
- Windows Command Prompt or PowerShell.

### 1. Clone the repository

Open a terminal and run:

```bash
git clone https://github.com/Krishna-gupta11/VYZN.git
cd VYZN
```

### 2. Create a virtual environment

```bash
py -m venv .venv
```

Activate it in Command Prompt:

```bat
.venv\Scripts\activate.bat
```

For PowerShell, use:

```powershell
.\.venv\Scripts\Activate.ps1
```

A virtual environment keeps the project's Python dependencies separate from other Python projects on your computer.

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Run VYZN

From the project root, in Command Prompt:

```bat
set PYTHONPATH=src
python -m vyzn.main
```

In PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m vyzn.main
```

VYZN should launch as a desktop application.

### 5. Run tests

If the required testing dependencies are installed, run:

```bash
python -m unittest discover -s tests
```

If the project uses a pytest-specific test setup, install pytest and use:

```bash
python -m pytest
```

Tests should be run against a development or test database, not a database containing important personal information.

---

## 📦 Build the Windows Executable

You can create a distributable Windows build from the source code.

### Requirements

- Windows 10/11.
- Python 3.11 or later recommended.
- The Python launcher, `py`.
- An internet connection for the initial dependency installation.

### Build instructions

1. Clone or download the source repository.
2. Extract the project if you downloaded a source archive.
3. Open the project folder.
4. Double-click `build_windows.bat`.
5. Wait for the dependencies and packaging process to finish.
6. Locate the generated application and archive.

The expected output paths are:

```text
dist/
├── VYZN/
│   ├── VYZN.exe
│   └── ...
└── VYZN_SHARE.zip
```

The exact output depends on the build script and the packaging environment.

### Distribute the application

Share `dist/VYZN_SHARE.zip` with users or attach it to a GitHub Release.

Users should extract the complete ZIP and run `VYZN.exe`. They should not need to install Python separately.

Build the Windows executable on Windows; this build process is intended for Windows distribution.

---

## 💾 How Data Storage Works

VYZN uses SQLite to store its local application data.

### When running from source

The development database is located at:

```text
data/vyzn.db
```

### When running the packaged application

The database is located at:

```text
%APPDATA%\VYZN\vyzn.db
```

To open this location on Windows, press `Win + R`, enter `%APPDATA%\VYZN`, and press Enter.

The packaged application uses a per-user data directory so that each Windows user can maintain a separate profile and progress history.

### Backups

Before the Clear All Data operation, VYZN creates a timestamped SQLite database backup in the applicable `backups` directory.

Development:

```text
data/backups/
```

Packaged application:

```text
%APPDATA%\VYZN\backups\
```

Keep backup files safe if you may need to recover previous progress. Do not delete your database or backup files unless you are sure you no longer need them.

### Clear All Data

The Profile section includes a guarded reset option for starting fresh. The reset requires confirmation and typing `RESET`.

It clears the supported personal profile and productivity records, including habits, tasks, notes, journal entries, important dates, and gamification progress. The selected theme is retained.

Always verify that a backup was created before relying on a reset to preserve your old data.

---

## 🔒 Privacy

VYZN is designed as a local-first desktop application.

- Personal productivity records are stored in the local SQLite database.
- The packaged application uses the current Windows user's application-data directory.
- Your database is not intentionally bundled into the distributable build.
- The project does not require a cloud account or remote database for its core local functionality.

Your data is still accessible to anyone who can access your Windows account and application files. Protect your computer and keep backups secure.

---

## ⚠️ Known Limitations

- VYZN is currently a Windows-focused desktop application.
- Calendar activity history depends on activity records stored by the application; older records may be incomplete if earlier versions did not record them.
- Progress analytics describe available records rather than predicting future behavior.
- The application is currently centered around a single main source module, `src/vyzn/main.py`.
- Local data is not automatically synchronized between computers.
- The application does not currently provide a shared multi-user cloud workspace.

---

## 🗺️ Roadmap

Potential future improvements include:

- More detailed habit statistics and visualizations.
- Additional profile customization.
- Improved calendar and reminder functionality.
- Data export and recovery improvements.
- Better separation of application modules.
- More automated tests and release checks.
- Additional accessibility and interface refinements.

The roadmap may change as development continues.

---

## 🤝 Contributing

Contributions, bug reports, and feature suggestions are welcome.

1. Fork the repository.
2. Create a branch for your change.
3. Make your changes and test them locally.
4. Commit your work with a clear message.
5. Open a pull request describing the changes.

Please avoid committing personal databases, backups, virtual environments, secrets, or generated build artifacts.

For bug reports, include the Windows version, Python version if applicable, steps to reproduce the issue, and any relevant error messages. Do not attach personal database files containing private information.

---

## Author

**Krishna Gupta**

Created as a personal productivity and habit-tracking desktop project.

**VYZN v1.0.0 — Build discipline. Track progress. Become your next version.**

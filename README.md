# VYZN — Personal Productivity Hub

VYZN is a local-first Windows desktop productivity app with a dark gaming-inspired UI, habits, tasks, notes, journal, a monthly calendar, activity analysis, progress ranks, XP, achievements, and color themes.

## Run from source (Windows 10/11)

Python 3.11+ is recommended. From the project root in Command Prompt:

```cmd
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
set PYTHONPATH=src
python -m vyzn.main
```

PowerShell equivalent for the final two commands:

```powershell
$env:PYTHONPATH = "src"
python -m vyzn.main
```

## New in this version

- **Profile:** edit the display name and motivational tagline; the name appears in the sidebar/dashboard greeting and the tagline appears on the dashboard.
- **Important dates:** add named dates with categories and optional notes, delete them later, and optionally repeat them yearly. The Calendar marks important dates with a ★ and shows their details when a date is selected.
- **Clear all data / start fresh:** Profile includes a guarded reset button. It requires confirmation and typing `RESET`, creates a timestamped SQLite backup in the `backups` folder under VYZN data, then clears habits, tasks, notes, journal, important dates, XP, quests, achievements, and profile customisation. The selected theme is retained.
- **Calendar:** navigable month grid, today shortcut, activity markers, a selected-day inspector, and task deadline markers/details for scheduled tasks.
- **Analysis:** current/best streak, total habit completions, tasks and journal totals, daily activity charts for the last 7 and 30 days, and a simple consistency readout.
- **Native charts:** activity charts are painted with Qt, so the app does not require Matplotlib.
- **Custom icon:** `assets/icons/VYZN.ico` is used for the Windows executable icon.
- Existing transactional habit/task XP updates, habit archiving, safer quest claims, and journal activity handling remain in place.

## Build a shareable Windows executable

Build this on a Windows 10/11 computer (the resulting build is intended for Windows, not macOS/Linux):

1. Extract the project folder somewhere writable.
2. Install Python 3.11+ from python.org and make sure the Python launcher (`py`) is available.
3. Double-click **`build_windows.bat`** and wait for it to finish. The first build downloads dependencies and may take several minutes.
4. The finished app folder is `dist\VYZN\` and the shareable archive is `dist\VYZN_SHARE.zip`.
5. Send the ZIP to your friends. They extract the entire ZIP, then double-click `VYZN.exe`. They do not need Python installed.

**Share the whole folder / ZIP, not only `VYZN.exe`.** PyInstaller's one-folder build includes required Qt libraries beside the executable. The executable uses the VYZN name and the custom icon embedded from `assets\icons\VYZN.ico`.

### Data and privacy

- During development, the database is `data\vyzn.db` inside the project.
- In the packaged executable, each Windows user gets their own database at `%APPDATA%\VYZN\vyzn.db`. This avoids trying to write into the app's installation folder and keeps each friend's progress separate.
- The build script does not package your development database, so your private habits, tasks, and journal are not shared with friends.
- VYZN stores automatic pre-reset backups in `data\backups` during development, or `%APPDATA%\VYZN\backups` in the packaged executable. Keep these backups somewhere safe if you may want to restore old progress.
- Back up your database before replacing an older build.

## Notes

- Calendar days display activity from the app's stored activity records; older data can be limited by what previous versions recorded.
- The Analysis page is descriptive, not a prediction model. It reports the records VYZN has available.
- The project is still intentionally centered in `src/vyzn/main.py` to preserve the customized interface while features are being stabilized.


## Task planning

Tasks support optional due dates, Low/Medium/High priority, optional details, and editing after creation. Overdue tasks are highlighted in the task list. The Calendar marks days with scheduled deadlines and lists tasks due on the selected date, including priority and completion state. Existing databases are migrated automatically; existing tasks remain without a deadline until you edit them.

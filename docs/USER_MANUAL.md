# NexusSMS — User Manual

Version: 1.0
Last updated: 2025-12-26

## Overview

NexusSMS is a Django-based school management and communications platform. It integrates core school functions (academics, attendance, finance, library, hostels, transport, assessments, analytics) and a communication layer for sending messages to students, parents, and staff.

This manual explains how to install, configure, and use the system from both an end-user and administrator perspective.

## Audience

- System administrators: installation, configuration, backup and maintenance
- School staff (teachers, registrars, finance officers): daily usage scenarios
- Admin users: user & permission management, system settings

## Requirements

- Python 3.8+ (the project uses a virtual environment)
- SQLite (default) or PostgreSQL for production
- Node.js (optional, for building frontend static assets)
- The project's Python dependencies listed in `requirements.txt`

## Quick start (development)

1. Clone the repo and create a virtualenv.

2. Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Apply migrations and create a superuser:

```powershell
python manage.py migrate
python manage.py createsuperuser
```

4. Run the development server:

```powershell
python manage.py runserver
```

5. Visit `http://127.0.0.1:8000/` and log in with the superuser.

## Configuration

- Settings are in `config/settings.py`. Use environment variables for secret keys, database credentials, and any third-party API keys (SMS gateways, email providers).
- Media files: by default `media/` is used. Ensure the directory is writable in production.
- Static files: collect static assets with `python manage.py collectstatic` before deploying.

## Apps & Features (high-level)

- `academics`: course, timetable and curriculum management
- `activities`: co-curricular activities and events
- `analytics`: dashboards and reports
- `assessment`: exam and grading workflows
- `attendance`: class attendance tracking
- `audit`: audit logs and change tracking
- `communication`: templates, SMS/email sending, messaging services
- `core`: site-wide settings, common models and utilities
- `finance`: billing, invoices, payments
- `library`: catalog and circulation
- `hostels`: resident/student housing management
- `transport`: routes, buses and student assignments
- `users`: authentication, profiles and roles

Each app exposes models, views, and admin interfaces. Use the Django admin to inspect and manage data quickly: `http://<host>/admin/`.

## User Roles & Permissions

- `Superuser`: full access to all features and settings
- `Staff/Admin`: role-based permissions assigned via the admin interface
- `Teacher`: access to class, attendance, assessment and related student data
- `Parent/Student`: limited portal access for viewing reports and messages

Permissions are managed through Django's built-in `auth` system and the custom permission checks implemented in individual apps.

## Common Workflows

- Create a student record: Admin → Users → Students → Add
- Mark attendance: Attendance → Select class/date → Save
- Record an assessment: Assessment → Exams → Create/Grade
- Generate a report: Analytics → Choose report → Export (CSV/PDF)
- Send SMS: Communication → Templates → Compose → Choose recipients → Send (ensure SMS gateway configured)

## Communication (SMS & Email)

1. Configure your SMS gateway credentials in `config/settings.py` or via environment variables.
2. Create message templates under `communication` to reuse standard texts.
3. Use the communication UI to target groups (classes, grades, parents, staff) or import recipient lists.

Note: For production, enable logging and rate-limiting for outgoing messages to stay within gateway quotas.

## Admin & Maintenance

- Backups: regularly export the database and media files. For SQLite copy `db.sqlite3`; for PostgreSQL use `pg_dump`.
- Migrations: when upgrading code, run `python manage.py migrate`.
- Static assets: run `python manage.py collectstatic` and ensure your webserver serves the `static/` directory.
- Logging: check `logs/` for app logs; configure a rotating log handler for production.

## Deployment Notes

- Use a WSGI server (e.g., Gunicorn + Nginx) or ASGI for channels/websockets.
- Use PostgreSQL for production databases and S3 (or equivalent) for media storage if needed.
- Configure HTTPS and secure cookies; keep `DEBUG = False` in production.

## Troubleshooting & FAQ

- If migrations fail, inspect `migrations/` folders for conflicting or missing migration files.
- If static files are not found, run `collectstatic` and confirm `STATIC_ROOT` is served by the webserver.
- Message sending fails: confirm gateway credentials, network access, and review `communication` app logs.

## Contributing & Development

- Follow the repo conventions for branches and pull requests.
- Run tests (if present) and linting before submitting PRs.

## Contact & Support

For internal deployments, list the system administrator's email and phone here. For external support, include your vendor/contact details.

---

This manual was created from the project's existing documentation and repository structure. If you'd like a version tailored to a specific role (teacher, parent, admin) or a printable PDF, tell me which format and I'll produce it.

## User Stories By Role

The following user stories describe typical tasks, acceptance criteria and success conditions for primary roles in NexusSMS. Use these stories to inform UI design, permissions, and test cases.

### Superuser

1. Title: Full system administration
	- As a `Superuser`, I want to configure site-wide settings (site name, timezone, SMS gateway credentials), so that the system runs with correct defaults.
	- Acceptance Criteria: I can edit settings in `config/settings.py` or via an admin UI; secret keys are stored via environment variables; changes persist and take effect after restart.

2. Title: Manage users and roles
	- As a `Superuser`, I want to create, edit and delete user accounts and assign roles/permissions, so that staff members have appropriate access.
	- Acceptance Criteria: I can add users via the admin and assign groups/permissions; role changes are honored across all apps immediately.

3. Title: Deploy and maintain backups
	- As a `Superuser`, I want to trigger backups and restore from backups, so that data can be recovered after incidents.
	- Acceptance Criteria: Backups of DB and `media/` can be created and restored; logs show result; restore process documented.

4. Title: Audit and logs
	- As a `Superuser`, I want to view audit logs of administrative actions, so that I can investigate changes.
	- Acceptance Criteria: Audit entries include user, timestamp, model changed and before/after values; filtering and export available.

### Staff / Admin (Registrar, Finance Officer)

1. Title: Student registration
	- As an `Admin`, I want to register new students with required fields (personal, guardian, enrolment), so that student records are available for other services.
	- Acceptance Criteria: Form validates required fields; student appears in `users` and `academics` apps; guardian contact details stored.

2. Title: Billing and invoices
	- As a `Finance Officer`, I want to create invoices and record payments, so that the school's financial records are accurate.
	- Acceptance Criteria: Invoice creation stores amounts, due dates and student/parent link; payments can be recorded and invoice status updates.

3. Title: Timetable & class allocations
	- As an `Admin`, I want to assign teachers to classes and manage timetables, so that schedules are published to teachers and students.
	- Acceptance Criteria: Class assignments map teacher→class→period; timetable exports and calendar feeds available.

4. Title: Reporting
	- As an `Admin`, I want to generate operational reports (admissions, attendance, outstanding fees), so that management gets actionable insights.
	- Acceptance Criteria: Reports are filterable by date, class and exportable to CSV/PDF.

### Teacher

1. Title: Mark attendance
	- As a `Teacher`, I want to mark attendance for my class quickly, so that daily attendance is recorded.
	- Acceptance Criteria: Teacher sees list of assigned students, can mark Present/Absent/Late, save per date; attendance impacts analytics.

2. Title: Record assessments and grades
	- As a `Teacher`, I want to create assessment entries and enter student grades, so that progress can be tracked.
	- Acceptance Criteria: Assessment has title, date, max score; teacher can enter scores per student; gradebook shows computed totals.

3. Title: Communicate with parents
	- As a `Teacher`, I want to send messages to parents of my students (SMS/email), so that I can quickly share updates.
	- Acceptance Criteria: Teacher selects class or individual students, chooses a template, and sends message; message status logged.

4. Title: Access student info
	- As a `Teacher`, I want to view student profiles, attendance history and assessment records, so I can support learners.
	- Acceptance Criteria: Teacher can open student profile and see consolidated info; access respects privacy permissions.

### Parent

1. Title: View child progress
	- As a `Parent`, I want to view my child's grades, attendance and upcoming events, so I can monitor progress.
	- Acceptance Criteria: Parent logs into portal, selects child, sees recent assessments, attendance summary and announcements.

2. Title: Receive notifications
	- As a `Parent`, I want to receive SMS/email alerts for key events (absent child, fee due, exam results), so that I stay informed.
	- Acceptance Criteria: Notifications sent according to communication templates; parent can opt in/out where policy allows.

3. Title: Update contact details
	- As a `Parent`, I want to update my contact information, so the school has correct details.
	- Acceptance Criteria: Parent can update phone/email via profile; changes are validated and reflected in communications.

### Student

1. Title: Access personal dashboard
	- As a `Student`, I want to view my timetable, grades and assignments, so I can prepare for classes.
	- Acceptance Criteria: Student logs into portal, sees today's timetable, recent grades and pending assignments.

2. Title: Submit assignments (if supported)
	- As a `Student`, I want to upload assignment submissions, so teachers can grade my work.
	- Acceptance Criteria: Upload accepts allowed file types, attaches to assessment entry, teacher notified.

### Cross-role & Edge Cases

- Bulk operations: Admins need bulk-import/CSV upload for users, students and invoices. Acceptance: imports with validation report and rollback option.
- Failed message delivery: System should log failures and queue retries; Admins should see failure reasons.
- Permission denial: Users presented with clear error messages and a path to request access.
- Data privacy: Sensitive fields masked for roles without permission; exports redact PII where policy requires.

If you'd like, I can split these into separate role-specific manuals (e.g., `docs/USER_MANUAL_TEACHER.md`), or convert this section into a printable PDF. Which format would you prefer next?

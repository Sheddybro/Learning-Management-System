NexusSMS — Detailed User Stories (permission-driven)

Version: 1.0
Last updated: 2025-12-26

Overview

This file expands role-based user stories using the application's role definitions and the permission mappings implemented in `apps/users/management/commands/assign_role_permissions.py`.

Role setup commands

- `python manage.py seed_staff_roles` — creates system staff roles.
- `python manage.py assign_role_permissions` — assigns permissions to seeded roles.
- `python manage.py sync_permissions` — syncs user permissions from assigned roles.

Super Administrator (super_admin)

Responsibilities:
- Full system configuration and institution-level management (`core.*` systemconfig, institutionuser, sequencegenerator).
- Create and manage all users, roles, and system-level resources.
- Run role seeding and permission sync management commands.
- View and export audit logs.

Representative permissions: all non-system permissions across apps (excludes `admin`, `contenttypes`, `sessions`, `sites`).

Typical user stories:
1. As a Super Administrator, I can create or update an `Institution` and global system settings so tenants run with correct defaults.
   - Acceptance: `core` models update and changes are visible to institution-scoped data.
2. As a Super Administrator, I can run `seed_staff_roles` and `assign_role_permissions` so every institution has the canonical roles and their permissions.
   - Acceptance: All expected `Role` objects exist and `Role.permissions` contains the expected permission strings.
3. As a Super Administrator, I can view and export audit logs for governance and troubleshooting.
   - Acceptance: `audit` entries include user, timestamp, model, action and before/after diffs; exports succeed.

School Administrator / Administrator (school_admin, admin)

Responsibilities:
- User and staff management (`users.*`).
- Admissions and application workflows (`users.*application`).
- Finance oversight (invoices, payments, fees, expenses, financial reports).
- Publish announcements and manage communication templates.
- View and manage basic academic session and institution-level settings.

Representative permissions: `users.*`, `finance.*`, `communication.*`, `academics.*` (session, class, enrollment management).

Typical user stories:
1. As an Administrator, I can onboard a student (create `User`, `UserProfile` and `Enrollment`) and link guardians so other apps can consume the record.
   - Acceptance: Student appears in `academics` enrollment and `users` tables; parent relations created.
2. As a Finance Officer, I can create invoices and record payments against students or guardians.
   - Acceptance: Invoice states progress correctly and payment entries reconcile to invoices; reports aggregate totals.
3. As an Administrator, I can schedule announcements and send messages to groups (class, grade, parents).
   - Acceptance: Recipients receive messages and the `communication` app logs delivery results.

Principal

Responsibilities:
- Academic oversight: timetables, enrollment, academic records, assessments and report cards.
- Attendance oversight and high-level performance monitoring.

Representative permissions: `academics.*` for enrollment/timetable/records, `assessment.*` for results/reportcards, `attendance.view_*`.

Typical user stories:
1. As a Principal, I can review aggregated assessment results and export school-level report cards.
   - Acceptance: Filtering and export functions produce expected aggregates.
2. As a Principal, I can inspect attendance summaries across classes and dates.
   - Acceptance: Attendance analytics reflect teacher input and display trends.

Department Head

Responsibilities:
- Manage department subjects, timetables and exams; supervise teachers in their department.

Representative permissions: teacher permissions plus `academics.add/change/view_subject`, `academics.add/change/view_timetable`, `assessment.add/change/view_exam`.

Typical user stories:
1. As a Department Head, I can create subjects for the department and assign teachers to those subjects.
   - Acceptance: Subjects persist and appear in timetables and enrollment screens.
2. As a Department Head, I can draft and publish department-level exams and view teacher-submitted marks.
   - Acceptance: Exam records are visible and marks roll up into department reports.

Teacher

Responsibilities:
- Classroom management: rosters, timetables, enrollment views.
- Class materials: upload/manage teaching resources.
- Assessment: publish assignments and record marks.
- Attendance: record daily and period attendance.
- Communication: send messages to students and guardians.

Representative permissions: `academics.view_*`, `academics.add/change/delete_classmaterial`, `assessment.add/change/view_assignment`, `assessment.add/change/view_mark`, `attendance.add/change/view_dailyattendance`, `communication.add_message`.

Typical user stories:
1. As a Teacher, I can open my class roster and mark each student Present/Absent/Late for each period.
   - Acceptance: `attendance` entries saved with author and date; analytics update.
2. As a Teacher, I can create an assignment, publish it to a class, and enter marks for students.
   - Acceptance: Assignment visible to students and marks stored in `assessment`.
3. As a Teacher, I can select a template and send an SMS/email to parents of my class.
   - Acceptance: Message queued and delivery status stored; SMS gateway credentials validated.

Accountant

Responsibilities:
- Fee structure creation, invoice generation, payment recording and financial reporting.

Representative permissions: `finance.*` (invoices, payments, feestructure, expenses, financialreport).

Typical user stories:
1. As an Accountant, I can create fee structures for a grade and bulk-generate invoices.
   - Acceptance: Invoices generated with correct amounts, assigned to students and queued for billing.
2. As an Accountant, I can record payments and reconcile outstanding invoices.
   - Acceptance: Payments applied to invoices and financial reports reflect updates.

Librarian

Responsibilities:
- Catalog management, circulation, reservations and fine payments.

Representative permissions: `library.*` (book, bookcopy, borrowrecord, reservation, finepayment, author, publisher, category).

Typical user stories:
1. As a Librarian, I can add book metadata and create book copies for circulation.
   - Acceptance: Copies listed and available for borrowing.
2. As a Librarian, I can record borrow/return transactions and compute fines where applicable.
   - Acceptance: Borrow records include due dates and fine records attach to user accounts.

Transport Manager & Driver

Transport Manager Responsibilities:
- Full CRUD for vehicles, drivers, attendants, routes, route stops, schedules and allocations.
- Manage maintenance, fuel logs and incident reporting.

Driver Responsibilities:
- View assigned routes/schedules, report incidents, submit fuel and maintenance records.

Representative permissions: `transport.*` for managers; drivers have limited `transport.view_*` and reporting permissions.

Typical user stories:
1. As a Transport Manager, I can publish route schedules and allocate students to buses.
   - Acceptance: Route manifests show assignments and driver details.
2. As a Driver, I can log an incident and upload fuel/maintenance logs.
   - Acceptance: Incident recorded and notified to transport manager; maintenance created.

Hostel Warden

Responsibilities:
- Manage hostels, rooms, beds, allocations, hostel fees, visitor logs, maintenance requests and inventory.

Representative permissions: `hostels.*` (hostel, room, bed, allocation, hostelfee, visitorlog, maintenancerequest, inventoryitem).

Typical user stories:
1. As a Hostel Warden, I can allocate a student to a bed and record hostel fees.
   - Acceptance: Allocation visible in student profile and hostel fee invoices updated.
2. As a Hostel Warden, I can log maintenance requests and track visitor logs.
   - Acceptance: Requests created and visitor logs searchable.

Activities Coordinator

Responsibilities:
- Plan and publish activities, manage registrations, equipment, budgets and competitions.

Representative permissions: `activities.*` (activity, activityenrollment, equipment, activitybudget, competition).

Typical user stories:
1. As an Activities Coordinator, I can open registration for an extracurricular activity and manage participants.
   - Acceptance: Enrolled participants appear on rosters and communication can target them.

Support Staff

Responsibilities:
- Provide user support, maintain help center content and view monitoring data for troubleshooting.

Representative permissions: `users.view_user`, `support.*`, `audit.view_auditlog`, `analytics.view_kpi`.

Typical user stories:
1. As Support Staff, I can view a user's profile and recent role activities to assist with account issues.
   - Acceptance: Support can access user details and escalate via internal messages/tickets; role changes are logged.

Counselor

Responsibilities:
- Student counseling, view academic/behavioral records and communicate with parents.

Representative permissions: `academics.view_academicrecord`, `assessment.view_result`, `attendance.view_dailyattendance`, `communication.add_message`.

Typical user stories:
1. As a Counselor, I can view a student's academic and behavioral history and message guardians privately.
   - Acceptance: Notes are recorded and messages logged; data access respects privacy rules.

Parent & Student (portal users)

Parents:
- View linked children's profiles, receive notifications, update contact details and view billing.

Students:
- View timetables, assignments, grades and submit work where enabled.

Typical user stories:
1. As a Parent, I can view my child's attendance summary, recent grades and outstanding fees via the portal.
   - Acceptance: Consolidated child view available and contact updates validated.
2. As a Student, I can view today's timetable and submit assignment files.
   - Acceptance: Submissions attach to the correct assessment and teacher receives notification.

Cross-role & Edge Cases

- Bulk imports: Admin CSV import must validate rows, report errors and support rollback on failure.
- Messaging failures: `communication` must log delivery failures and expose retry/failure reasons.
- Permission maintenance: Roles seeded via `seed_staff_roles`, permissions assigned by `assign_role_permissions`, and user permissions synchronized via `sync_permissions`.
- Data privacy: Exports and views must respect role-based redaction; PII limited to roles with explicit view permissions.

Next steps

If you'd like, I can:
- Split these stories into separate `docs/USER_STORIES_<ROLE>.md` files.
- Produce a CSV mapping `role,permission` for audit and review.
- Generate a printable PDF or stakeholder-facing condensed manual per role.

Tell me which output you prefer and I'll generate it.

---

Role Emojis & Considerations (Cons)

To make the document easier to scan and to highlight risks/considers, below are emoji labels for roles and short "cons" (considerations/risks) to keep in mind when implementing features or granting permissions.

- Super Administrator 🛡️ — Cons: High blast radius for mistakes; enforce MFA, strict audit and change approvals.
- School Administrator / Administrator 🧑‍💼 — Cons: Financial and bulk-data operations can cause billing or data integrity issues; add validation and approval flows.
- Principal 🧑‍🏫 — Cons: Access to aggregated student data requires privacy controls and staged publishing for results.
- Department Head 🧑‍🔬 — Cons: Timetable/subject changes cascade; provide review/confirm steps.
- Teacher 👩‍🏫 — Cons: UI must be fast for daily tasks; ensure messaging honors opt-outs and quotas.
- Accountant 💰 — Cons: Financial changes need validation, audit trail and possible approval steps.
- Librarian 📚 — Cons: Catalog imports need deduplication and metadata validation.
- Transport Manager & Driver 🚌 — Cons: Real-time updates must sync reliably; offline reporting for drivers may be needed.
- Hostel Warden 🛏️ — Cons: Resident data is sensitive; access controls and visitor log privacy required.
- Activities Coordinator 🏅 — Cons: Event overbooking and budget control; enforce capacity and budget checks.
- Support Staff 🛠️ — Cons: Give read-only access to sensitive data; avoid role-change privileges.
- Counselor 💬 — Cons: Counseling notes are sensitive; limit access and consider encrypted storage.
- Parent & Student 👪 — Cons: Strict PII protection; parents/students must only see authorized child/student data.

If you'd like, I can inline these emojis into the main headings of the role sections, split the document into per-role files, or export a CSV mapping `role,permission,emoji,consideration` for review.

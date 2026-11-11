# Commercial SaaS modernization — audit and delivery plan

Status: Phase 1 in progress (2026-11-11). This is an implementation plan, not a
claim that the README's workflows have all been built or tested.

## Baseline and README mapping

The README defines fifteen roles and acceptance scenarios across institution
management, academics, enrollment, assessment, finance, attendance, messaging,
library, hostel, transportation, health, activities, support and analytics.
The Django repository has corresponding apps and many views/templates, but most
README acceptance scenarios do not have automated tests asserting their behavior.

| Area | Current observation | Priority |
| --- | --- | --- |
| Tenant isolation | Middleware accepted school IDs from sessions before validating membership; fixed in Phase 1 candidate and covered by regression tests. View/queryset and serializer isolation still require a full audit. | P0 |
| Role authorization | Extensive custom role models and view permissions exist; verify every object-level read/write and tenant-scoped role before release. | P0 |
| Production secrets | SECRET_KEY is environment-loaded; credentials must never be committed. Verify startup fails closed when unset in production. | P0 |
| Data integrity | `makemigrations --check --dry-run` currently detects an uncommitted `users.UserRole.is_primary` migration. Resolve by reviewing intended schema before production database changes. | P0 |
| Authentication | django-allauth shows four deprecated-settings warnings. Update compatibility settings with login/signup regression coverage. | P1 |
| School onboarding | Institution creation exists; commercial trial lifecycle and self-service subscription provisioning are not established by the README implementation. | P1 |
| SaaS billing | School fee/invoice workflows exist; platform subscription plans, Paystack callbacks, webhook signature verification and idempotency require separate design and implementation. | P1 |
| Database | SQLite currently configured; plan a tested PostgreSQL migration with backup, consistency verification and rollback. | P1 |
| Email | Console backend used during deployment; production transactional email provider and delivery tests are outstanding. | P1 |
| Frontend | Existing templates are extensive; create a shared accessible responsive design system and migrate routes incrementally. | P2 |
| Automated QA | README names test technologies, but actual feature tests are sparse; construct a seeded multi-tenant test matrix and browser journeys. | P0 |

## Execution sequence and gates

1. **Security and characterization:** Establish CI; test authentication, session and
   hostname tenancy, cross-school object access, permissions and existing data
   migrations. Fix P0 problems on a reviewable branch. Do not deploy until full
   targeted tests, migration checks and backup/rollback steps pass.
2. **SaaS domain model:** Add explicit platform owner vs school owner roles,
   tenant-scoped RBAC, school lifecycle, invitation/onboarding, subscriptions,
   plans, trials and entitlements. Use safe migrations without dropping tables.
3. **Billing:** Integrate Paystack server-side with environment-secret keys,
   verified signed webhooks, idempotent payment processing, renewal/grace periods,
   retries and ledger/audit events; test in sandbox before live payments.
4. **Academics and operations:** Complete each README acceptance scenario for
   teachers, parents, students, admissions, assessment, attendance, finance,
   library, transport, hostels, health, activities, support and analytics.
5. **Premium UI/UX:** Unify navigation, components, design tokens, forms,
   notifications and mobile accessibility without breaking existing URLs.
6. **Infrastructure:** Rehearse SQLite-to-PostgreSQL copy, validation and rollback;
   configure background tasks, transactional email, object storage, monitoring,
   backups and environment-specific deployment secrets as hosting permits.
7. **Release:** Run unit, integration, tenant-security, browser, accessibility,
   performance and regression suites; release by small batches with monitoring.

## Required client applications

- **Desktop:** An installable, accessible desktop client for Windows (and a
  documented macOS/Linux path), with school/role aware navigation and update
  distribution. The shared web manifest/service-worker foundation is an early
  step, **not** proof of a signed desktop installer.
- **Mobile:** A distributable Android APK (and an iOS packaging plan) that
  authenticates securely to the same Django API and respects school tenancy.
  A responsive Django website or PWA alone does not meet the APK requirement.
- **Shared backend:** School records, permissions and subscriptions remain on
  the Django SaaS server; do not cache sensitive school data in the browser
  service worker. Design mobile token storage, logout, session expiry, push
  notifications and offline constraints before enabling native persistence.
- **Release gates:** Build and inspect actual desktop/mobile artifacts, verify
  login and role-limited journeys on target devices, and publish tested download
  links on the PythonAnywhere website only after signing/versioning decisions.

## Guardrails

- Keep the existing PythonAnywhere site serving until a replacement is validated.
- Never rewrite or delete user records, migrations or the production database as
  part of an untested design change.
- No live Paystack charge, account credential, DNS change or production data
  migration before the relevant explicit approval and verification.
- A green Django `check` does not prove README-level functional completeness.

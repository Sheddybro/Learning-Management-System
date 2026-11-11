# Finance receipt and overdue-payment verification

This branch triggers the repository CI workflows against the finance changes currently committed to `main`.

## Latest additions

- Students can open and print a receipt only for a completed payment attached to their own invoice.
- The receipt page returns students to their own invoice rather than a staff-only page.
- Staff receipts remain scoped to institutions the signed-in user can access.
- Payment forms allow recording payments against overdue invoices.
- Previous finance hardening remains in place: transactional/idempotent payment accounting, reversal on cancellation or soft deletion, overpayment protection, school-scoped forms and object access, and student-owned invoice details.

## Required checks

- `python manage.py check --settings=config.audit_settings`
- `python manage.py test apps.finance.test_payment_safety --settings=config.audit_settings --verbosity=2`
- Existing Django security/regression, leave workflow, and public/authenticated smoke tests.

The latest additions must pass CI before being marked verified. Browser viewport testing and PythonAnywhere deployment are still separate follow-up tasks. No production database or hosting deployment is changed by this branch.

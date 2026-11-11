# Finance hardening and regression scope

This branch is a CI verification request for the finance changes already committed to `main`.

## Changes included on main

- Make completed-payment accounting idempotent and transactional.
- Reverse invoice balances when completed payments are cancelled, reversed, or soft-deleted.
- Reject overpayments and enforce that payment, invoice, student, and institution agree.
- Scope invoice, payment, expense, fee structure, fee discount, and financial report detail/edit/delete lookups by school.
- Scope finance form choices and current academic-session dropdowns to the active institution.
- Correct invoice and payment form student choices to use Student profiles rather than User records.
- Add a dedicated student-owned invoice detail page and responsive printable receipt page.
- Remove false payment-success callbacks when no payment gateway is configured.
- Add regression coverage for invoice ownership, payment idempotency, reversal, overpayment, and receipt rendering.

## Required CI checks

- Django system checks using `config.audit_settings`.
- Finance safety and student UI regression tests:
  `python manage.py test apps.finance.test_payment_safety --settings=config.audit_settings --verbosity=2`

## Verification caveat

These tests have been added but must pass in GitHub Actions before this finance pass is considered verified. Browser-based end-to-end checks and PythonAnywhere deployment are separate follow-up steps. No production database or deployment is changed by this branch.

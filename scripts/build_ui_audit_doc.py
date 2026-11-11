"""Build an evidence-first Word audit from recorded route statuses and real screenshots."""
import csv
from collections import Counter
from datetime import date
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "audit"
OUTPUT = AUDIT / "School_Web_and_Mobile_UI_Functional_Audit.docx"


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Shading Accent 1"
    for cell, value in zip(table.rows[0].cells, headers):
        cell.text = str(value)
    for values in rows:
        for cell, value in zip(table.add_row().cells, values):
            cell.text = str(value)


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.header_distance = Inches(.4)
    sec.footer_distance = Inches(.4)
    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(9)
    doc.add_heading("School Management System", 0)
    doc.add_paragraph("Multi-role functional and UI audit — evidence and remediation register")
    doc.add_paragraph("11 November 2026  |  Project: Sheddybro/Learning-Management-System")
    doc.add_paragraph("Status: PARTIAL / IN PROGRESS. This report distinguishes actual screenshots, automated HTTP checks, and areas not yet verified. It is not a certification of complete application functionality.")

    doc.add_heading("1. Method and environment", 1)
    for line in [
        "Source review: Django URLs, models, class-based views, templates, permissions and local changes.",
        "Isolation: automated GET checks use a dedicated SQLite audit database with fictional users; live student data is not touched.",
        "Roles: anonymous visitor, superadministrator, school administrator, teacher, student, parent, accountant and librarian.",
        "Web UI evidence: actual screenshots of the public PythonAnywhere site (desktop browser).",
        "Mobile-web responsive and Expo native Android screenshots: NOT CAPTURED. No working emulated device or phone-sized browser viewport was available in this run. These cannot be inferred from desktop screenshots.",
        "Object-detail pages requiring IDs, POST/PUT/DELETE workflows, file uploads and payment flows are not covered by the argument-free GET matrix.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    matrix_file = AUDIT / "role_permission_matrix.csv"
    rows = list(csv.DictReader(matrix_file.open(encoding="utf-8"))) if matrix_file.exists() else []
    roles = ["guest", "superadmin", "school_admin", "teacher", "student", "parent", "accountant", "librarian"]
    doc.add_heading("2. Automated role/route matrix", 1)
    baseline_file = AUDIT / "role_permission_matrix_baseline.csv"
    baseline = list(csv.DictReader(baseline_file.open(encoding="utf-8"))) if baseline_file.exists() else []
    baseline_errors = sum(
        row.get(role, "").startswith("ERROR")
        for row in baseline for role in roles
    )
    current_errors = sum(
        row.get(role, "").startswith("ERROR")
        for row in rows for role in roles
    )
    doc.add_paragraph(f"Route records captured: {len(rows)}. A route record may have up to eight role responses. SKIP_ACTION means a potentially mutating endpoint was intentionally not called.")
    if baseline:
        doc.add_paragraph(
            f"Full-sweep comparison: {baseline_errors} exceptions over {len(baseline)} routes initially, "
            f"versus {current_errors} exceptions over {len(rows)} routes in the subsequent sweep. "
            f"The measured reduction is {baseline_errors-current_errors} exception responses. "
            "The runs differ slightly in route inventory and were executed against sparse test fixtures; these counts are not an exact production defect count."
        )
    doc.add_paragraph("The matrix is a baseline snapshot taken before the final targeted repairs listed below. Some errors in this snapshot have therefore already been corrected locally; no full rerun has yet established a new total.")
    counts = []
    for role in roles:
        count = Counter(row.get(role, "") for row in rows)
        counts.append([role, count["200"], sum(n for status, n in count.items() if status.startswith("30")), count["403"], count["404"], sum(n for status, n in count.items() if status.startswith("5") or status.startswith("ERROR")), count["SKIP_ACTION"]])
    add_table(doc, ["Role", "200", "3xx", "403", "404", "5xx/error", "Skipped"], counts)
    doc.add_paragraph("Important: an HTTP 200 only confirms the page returned a response; it does not prove that the content, data isolation, interactive controls, or permission design is correct. Redirects require destination inspection. Exceptions can be due to missing fixture data or defects; each needs triage.")
    errors = []
    for row in rows:
        for role in roles:
            response = row.get(role, "")
            if response.startswith("5") or response.startswith("ERROR"):
                errors.append((row["name"], role, response[:115]))
    doc.add_heading("Observed exceptions requiring triage (sample)", 2)
    add_table(doc, ["URL name", "Role", "Result"], errors[:20] or [["None recorded", "—", "—"]])
    if len(errors) > 20:
        doc.add_paragraph(f"Only the first 20 of {len(errors)} recorded 5xx/exceptions are printed here. The full role_permission_matrix.csv is the underlying machine-readable record.")

    targeted_file = AUDIT / "targeted_regression_matrix.csv"
    if targeted_file.exists():
        targeted = list(csv.DictReader(targeted_file.open(encoding="utf-8")))
        result_counts = Counter(row["result"] for row in targeted)
        doc.add_heading("Post-repair targeted smoke checks", 2)
        doc.add_paragraph(
            f"{len(targeted)} authenticated/guest GET outcomes were collected across "
            f"{len(set(row['role'] for row in targeted))} role types and "
            f"{len(set(row['route'] for row in targeted))} repaired routes. "
            f"Smoke outcome: {result_counts['PASS']} pass, "
            f"{result_counts['FAIL']} exceptions/5xx, "
            f"{result_counts['REVIEW']} guest status reviews. "
            "These checks demonstrate response availability, not complete authorization correctness."
        )
        add_table(doc, ["Route", "Superadmin", "Teacher", "Student", "Guest"], [
            [name, *[
                next((str(row["status"]) for row in targeted if row["route"] == name and row["role"] == role), "—")
                for role in ("superadmin", "teacher", "student", "guest")
            ]]
            for name in sorted(set(row["route"] for row in targeted))
        ])

    doc.add_heading("3. Confirmed defects and fixes", 1)
    add_table(doc, ["Finding", "Impact", "Action / current status"], [
        ["Anonymous role-test exceptions", "Protected create views could access AnonymousUser.user_roles and raise 500 instead of redirecting to sign-in.", "Changed shared AuthenticatedRoleTestMixin to authenticate before testing roles. Django system check passed; full integration verification pending."],
        ["Committee dashboard guest exception", "Local academic committee mixin accessed AnonymousUser.teacher_profile without checking authentication.", "Added LoginRequiredMixin and a missing-profile guard; targeted guest requests now return HTTP 302 for both committee dashboard and class creation."],
        ["Principal dashboards NameError", "Several principal pages referenced an unimported role-check helper.", "Added the missing helper import. Principal teacher-management GET now returns 200 in the isolated superadmin test."],
        ["Transport reports NameError and scope", "Summary report referenced accessible_insts outside its scope; a failed lookup could otherwise expose all-school reporting data.", "Passed accessible institution scope into summary generation and made lookup failures fail closed. Superadmin report GET now returns 200."],
        ["Duplicate library sign-in", "The library's separate sign-in route referenced a missing template.", "Redirects to the shared login page. Tested HTTP 302 to /users/login/."],
        ["Analytics form model import", "Analytics forms imported AcademicSession from the wrong Django app.", "Corrected three imports. Further analytics defects remain and are not marked resolved."],
        ["Hostel mobile API field and access scope", "The API attempted to select a calculated Python property as a database field and did not restrict results by school.", "Now serializes available_beds from each Hostel instance and filters non-superusers by accessible institutions; local school-admin GET returned HTTP 200 with an empty fixture list."],
        ["Analytics report list and links", "Views referenced a nonexistent User.role_type method and templates reversed missing or malformed report URLs.", "Uses real user-role memberships and institution-scoped report queries. Added a report-type selection page, CSV export, owner-only POST delete, and removed unimplemented retry/duplicate controls. Report list, selector, API and CSV export returned HTTP 200 for superadmin, teacher and student."],
        ["Analytics default dashboard", "Creating a user's dashboard without its required institution triggered database integrity failures.", "The dashboard now attaches the user's institution; missing assignments fail closed. Dashboard GET returned 200 for superadmin, teacher and student fixtures."],
        ["Activity competition counters", "A template filter attempted database filtering after pagination had sliced the queryset.", "Counter filters now support sliced querysets; competition listing returned HTTP 200."],
        ["Activity and enrolment links", "Rendered JavaScript used invalid numeric placeholders in UUID URL patterns, causing template reverse errors.", "Correct UUID placeholders and a secure bulk-status POST endpoint implemented. Activity list, my activities and enrolment list returned HTTP 200 in targeted tests."],
        ["Activity equipment and budget pages", "List and form templates were absent, and several view querysets lacked explicit institution restrictions.", "Added responsive Bootstrap-based list/form pages, institution filters, creation assignment, and a valid equipment-update redirect; list/create pages returned HTTP 200."],
        ["Attendance page redirect", "An attendance redirect used an unnamespaced route name.", "Corrected redirect to the attendance namespace; targeted student request now redirects successfully."],
        ["Unordered library pagination", "Changing result order could repeat/skip records between pages.", "Added stable primary-key ordering to author, library member, publisher and book category list querysets."],
        ["Legacy public-page claims", "Live landing page displays unsubstantiated alumni, years, acceptance and ratio figures.", "Local revised guest landing page removes invented figures; live deployment remains outstanding."],
        ["Legacy login controls", "Live sign-in includes contradictory remember/secure options and social sign-in controls of uncertain function.", "Local updated login removes redundant controls; deployment and UI retest pending."],
    ])

    doc.add_heading("4. Actual live browser screenshots", 1)
    shots = [
        ("Public homepage", "https://learningmanagementsystem.pythonanywhere.com/users/", "live_home_desktop.jpg", "Promotional numerical claims appear on the current live site."),
        ("Sign-in page", "https://learningmanagementsystem.pythonanywhere.com/users/login/", "live_login_desktop.jpg", "Shows existing login form and redundant controls on the current live deployment."),
        ("Application portal", "https://learningmanagementsystem.pythonanywhere.com/users/application-portal/", "live_application_desktop.jpg", "Guest-visible application portal and navigation surface."),
    ]
    for title, url, name, note in shots:
        img = AUDIT / "screenshots" / name
        if not img.exists():
            continue
        doc.add_page_break()
        doc.add_heading(title, 2)
        doc.add_paragraph(f"Source URL: {url}")
        doc.add_picture(str(img), width=Inches(6.25))
        doc.add_paragraph(note)

    doc.add_heading("5. Outstanding acceptance tests", 1)
    for line in [
        "Render representative authenticated dashboard and CRUD pages for each role at desktop width and phone-sized viewport; save genuine captures alongside expected/actual outcomes.",
        "Test that a student cannot access teachers' records, that parents see only linked children, and that staff users cannot cross institutions by guessed record URLs.",
        "Exercise create/edit/delete, validation, search, filters, pagination, uploads, messaging, attendance, finance, hostel, transport and library journeys using realistic fixtures.",
        "Run the Expo Android app in an emulator/handset and capture native screens for sign-in, role-specific navigation, forms, errors and network-loss states.",
        "Deploy reviewed UI and backend changes through the project's normal release process; retake screenshots against the deployed build and rerun full integration tests.",
    ]:
        doc.add_paragraph(line, style="List Bullet")

    doc.add_paragraph("Evidence integrity: embedded images are direct captures of the live school site. No screenshot is synthetically generated or portrayed as mobile testing.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()

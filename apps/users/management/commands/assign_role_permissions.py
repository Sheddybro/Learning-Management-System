from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from apps.users.models import Role


class Command(BaseCommand):
    help = "Assign appropriate permissions to all staff roles"

    def handle(self, *args, **options):
        # Define permissions for each role type
        role_permissions = {
            "super_admin": self._get_super_admin_permissions(),
            "school_admin": self._get_school_admin_permissions(),  # School admin gets all permissions except super-admin only ones
            "admin": self._get_admin_permissions(),
            "principal": self._get_principal_permissions(),
            "department_head": self._get_department_head_permissions(),
            "counselor": self._get_counselor_permissions(),
            "teacher": self._get_teacher_permissions(),
            "accountant": self._get_accountant_permissions(),
            "librarian": self._get_librarian_permissions(),
            "activities_coordinator": self._get_activities_coordinator_permissions(),
            "driver": self._get_driver_permissions(),
            "support": self._get_support_permissions(),
            "transport_manager": self._get_transport_manager_permissions(),
            "hostel_warden": self._get_hostel_warden_permissions(),
        }

        total_assigned = 0

        for role_type, permissions in role_permissions.items():
            try:
                # Get all roles with this role_type across all institutions
                roles = Role.objects.filter(role_type=role_type)
                if not roles.exists():
                    self.stdout.write(
                        self.style.WARNING(f"No roles found for {role_type}, skipping")
                    )
                    continue

                roles_assigned = 0
                for role in roles:
                    # Guard against roles with missing institution references (data integrity issues)
                    try:
                        institution_name = role.institution.name
                    except Exception as inst_err:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Role '{role.name}' has missing institution (id={getattr(role, 'institution_id', None)}): {inst_err} - skipping"
                            )
                        )
                        continue
                    self.stdout.write(
                        f"Assigning permissions to {role.name} (Institution: {institution_name})..."
                    )

                    # Clear existing permissions and assign new ones
                    role.permissions.clear()

                    role_assigned = 0
                    for perm_codename in permissions:
                        try:
                            app_label, codename = perm_codename.split(".", 1)
                            permission = Permission.objects.get(
                                content_type__app_label=app_label, codename=codename
                            )

                            if not role.permissions.filter(pk=permission.pk).exists():
                                role.permissions.add(permission)
                                role_assigned += 1
                                total_assigned += 1

                        except Permission.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Permission not found: {perm_codename} - skipping"
                                )
                            )
                        except ValueError:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Invalid permission format: {perm_codename}"
                                )
                            )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Assigned {role_assigned} permissions to {role.name}"
                        )
                    )
                    roles_assigned += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Assigned permissions to {roles_assigned} roles for {role_type}"
                    )
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error assigning permissions to {role_type}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"Total permissions assigned: {total_assigned}")
        )

    def _get_super_admin_permissions(self):
        """Super admin gets all permissions from all apps"""
        permissions = []
        for perm in Permission.objects.all():
            # Skip system Django permissions that shouldn't be assigned
            if perm.content_type.app_label not in [
                "admin",
                "contenttypes",
                "sessions",
                "sites",
            ]:
                permissions.append(f"{perm.content_type.app_label}.{perm.codename}")
        return permissions

    def _get_school_admin_permissions(self):
        """School admin gets all permissions except super-admin only ones"""
        permissions = []
        # Permissions that should remain super-admin only
        excluded_perms = [
            "core.add_institutionuser",
            "core.change_institutionuser",
            "core.delete_institutionuser",
            "core.view_institutionuser",
            "core.add_sequencegenerator",
            "core.change_sequencegenerator",
            "core.delete_sequencegenerator",
            "core.view_sequencegenerator",
            "core.add_systemconfig",
            "core.change_systemconfig",
            "core.delete_systemconfig",
            "core.view_systemconfig",
        ]

        for perm in Permission.objects.all():
            perm_str = f"{perm.content_type.app_label}.{perm.codename}"
            # Skip system Django permissions that shouldn't be assigned
            if perm.content_type.app_label in [
                "admin",
                "contenttypes",
                "sessions",
                "sites",
            ]:
                continue
            # Skip excluded permissions
            if perm_str in excluded_perms:
                continue
            permissions.append(perm_str)
        return permissions

    def _get_admin_permissions(self):
        """School Admin gets permissions aligned with Features.md: Staff, Finance, Communication"""
        permissions = [
            # Users management (Staff)
            "users.add_user",
            "users.change_user",
            "users.delete_user",
            "users.view_user",
            "users.add_userprofile",
            "users.change_userprofile",
            "users.view_userprofile",
            "users.add_role",
            "users.change_role",
            "users.view_role",
            # Application management (Staff)
            "users.add_studentapplication",
            "users.change_studentapplication",
            "users.delete_studentapplication",
            "users.view_studentapplication",
            "users.add_staffapplication",
            "users.change_staffapplication",
            "users.delete_staffapplication",
            "users.view_staffapplication",
            # Core system permissions (Institution management)
            "core.view_institution",
            "core.change_institution",
            "core.add_institution",
            # Finance (aligned with Features.md)
            "finance.add_invoice",
            "finance.change_invoice",
            "finance.delete_invoice",
            "finance.view_invoice",
            "finance.add_payment",
            "finance.change_payment",
            "finance.delete_payment",
            "finance.view_payment",
            "finance.add_feestructure",
            "finance.change_feestructure",
            "finance.delete_feestructure",
            "finance.view_feestructure",
            "finance.add_expense",
            "finance.change_expense",
            "finance.delete_expense",
            "finance.view_expense",
            "finance.add_financialreport",
            "finance.change_financialreport",
            "finance.delete_financialreport",
            "finance.view_financialreport",
            # Communication (aligned with Features.md)
            "communication.add_announcement",
            "communication.change_announcement",
            "communication.delete_announcement",
            "communication.view_announcement",
            "communication.add_message",
            "communication.change_message",
            "communication.view_message",
            # Academic session management (aligned with Features.md)
            "academics.add_academicsession",
            "academics.change_academicsession",
            "academics.view_academicsession",
            # Academic management permissions
            "academics.add_department",
            "academics.change_department",
            "academics.delete_department",
            "academics.view_department",
            "academics.add_subject",
            "academics.change_subject",
            "academics.delete_subject",
            "academics.view_subject",
            "academics.add_gradelevel",
            "academics.change_gradelevel",
            "academics.delete_gradelevel",
            "academics.view_gradelevel",
            "academics.add_class",
            "academics.change_class",
            "academics.delete_class",
            "academics.view_class",
            "academics.add_enrollment",
            "academics.change_enrollment",
            "academics.delete_enrollment",
            "academics.view_enrollment",
            # System configuration access
            "core.view_systemconfig",
        ]
        return permissions

    def _get_principal_permissions(self):
        """Principal gets academic leadership permissions aligned with Features.md"""
        return [
            # Academic leadership and oversight (Features.md: Academic Leadership, Performance, Teacher Management)
            "academics.view_department",
            "academics.view_subject",
            "academics.view_class",
            "academics.add_enrollment",
            "academics.change_enrollment",
            "academics.view_enrollment",
            "academics.add_timetable",
            "academics.change_timetable",
            "academics.view_timetable",
            "academics.add_academicrecord",
            "academics.change_academicrecord",
            "academics.view_academicrecord",
            # Assessment and performance monitoring
            "assessment.view_assignment",
            "assessment.view_mark",
            "assessment.add_result",
            "assessment.change_result",
            "assessment.view_result",
            "assessment.add_reportcard",
            "assessment.change_reportcard",
            "assessment.view_reportcard",
            "academics.view_achievement",
            "academics.view_behaviorrecord",
            # Attendance oversight
            "attendance.view_dailyattendance",
            "attendance.view_attendancesummary",
            # Communication for stakeholder engagement
            "communication.add_announcement",
            "communication.change_announcement",
            "communication.view_announcement",
            "communication.add_message",
            "communication.view_message",
        ]

    def _get_department_head_permissions(self):
        """Department head gets department-specific permissions"""
        permissions = self._get_teacher_permissions()
        permissions.extend(
            [
                "academics.add_subject",
                "academics.change_subject",
                "academics.view_subject",
                "academics.add_timetable",
                "academics.change_timetable",
                "academics.view_timetable",
                "assessment.add_exam",
                "assessment.change_exam",
                "assessment.view_exam",
            ]
        )
        return permissions

    def _get_counselor_permissions(self):
        """Counselor gets student support permissions"""
        return [
            "academics.view_class",
            "academics.view_academicrecord",
            "assessment.view_result",
            "assessment.view_reportcard",
            "assessment.view_mark",
            "attendance.view_dailyattendance",
            "attendance.view_attendancesummary",
            "academics.view_behaviorrecord",
            "communication.add_message",
            "communication.view_message",
        ]

    def _get_teacher_permissions(self):
        """Teacher gets classroom management permissions"""
        return [
            # Academic
            "academics.view_department",
            "academics.view_subject",
            "academics.view_class",
            "academics.view_enrollment",
            "academics.view_timetable",
            "academics.add_classmaterial",
            "academics.change_classmaterial",
            "academics.delete_classmaterial",
            "academics.view_classmaterial",
            "academics.view_academicrecord",
            # Assessment
            "assessment.add_assignment",
            "assessment.change_assignment",
            "assessment.delete_assignment",
            "assessment.view_assignment",
            "assessment.add_mark",
            "assessment.change_mark",
            "assessment.view_mark",
            "assessment.view_result",
            # Attendance
            "attendance.add_dailyattendance",
            "attendance.change_dailyattendance",
            "attendance.view_dailyattendance",
            "attendance.view_attendancesession",
            "attendance.view_periodattendance",
            # Communication
            "communication.add_message",
            "communication.view_message",
        ]

    def _get_accountant_permissions(self):
        """Accountant gets finance permissions"""
        return [
            "finance.add_invoice",
            "finance.change_invoice",
            "finance.delete_invoice",
            "finance.view_invoice",
            "finance.add_payment",
            "finance.change_payment",
            "finance.delete_payment",
            "finance.view_payment",
            "finance.add_feestructure",
            "finance.change_feestructure",
            "finance.delete_feestructure",
            "finance.view_feestructure",
            "finance.add_expense",
            "finance.change_expense",
            "finance.delete_expense",
            "finance.view_expense",
            "finance.add_financialreport",
            "finance.change_financialreport",
            "finance.delete_financialreport",
            "finance.view_financialreport",
        ]

    def _get_librarian_permissions(self):
        """Librarian gets library permissions"""
        return [
            "library.add_library",
            "library.change_library",
            "library.delete_library",
            "library.view_library",
            "library.add_author",
            "library.change_author",
            "library.delete_author",
            "library.view_author",
            "library.add_publisher",
            "library.change_publisher",
            "library.delete_publisher",
            "library.view_publisher",
            "library.add_bookcategory",
            "library.change_bookcategory",
            "library.delete_bookcategory",
            "library.view_bookcategory",
            "library.add_book",
            "library.change_book",
            "library.delete_book",
            "library.view_book",
            "library.add_bookcopy",
            "library.change_bookcopy",
            "library.delete_bookcopy",
            "library.view_bookcopy",
            "library.add_librarymember",
            "library.change_librarymember",
            "library.delete_librarymember",
            "library.view_librarymember",
            "library.add_borrowrecord",
            "library.change_borrowrecord",
            "library.delete_borrowrecord",
            "library.view_borrowrecord",
            "library.add_reservation",
            "library.change_reservation",
            "library.delete_reservation",
            "library.view_reservation",
            "library.add_finepayment",
            "library.change_finepayment",
            "library.delete_finepayment",
            "library.view_finepayment",
        ]

    def _get_driver_permissions(self):
        """Driver gets transport permissions for route execution and safety reporting"""
        return [
            # Route execution permissions (aligned with Features.md)
            "transport.view_vehicle",
            "transport.view_route",
            "transport.view_routeschedule",
            "transport.change_route",
            "transport.change_routeschedule",  # For route updates during execution
            # Fuel and maintenance reporting
            "transport.add_fuelrecord",
            "transport.change_fuelrecord",
            "transport.view_fuelrecord",
            "transport.add_maintenancerecord",
            "transport.change_maintenancerecord",
            "transport.view_maintenancerecord",
            # Safety and incident reporting
            "transport.add_incidentreport",
            "transport.change_incidentreport",
            "transport.view_incidentreport",
            # Transport allocations (view only for assigned routes)
            "transport.view_transportallocation",
        ]

    def _get_support_permissions(self):
        """Support staff gets technical support and system monitoring permissions"""
        return [
            # User support
            "users.view_user",
            "users.view_userprofile",
            # Communication for support
            "communication.add_message",
            "communication.view_message",
            "communication.add_announcement",
            "communication.view_announcement",
            # Help center management
            "support.add_helpcenterarticle",
            "support.change_helpcenterarticle",
            "support.view_helpcenterarticle",
            "support.add_faq",
            "support.change_faq",
            "support.view_faq",
            "support.add_resource",
            "support.change_resource",
            "support.view_resource",
            # System monitoring (aligned with Features.md)
            "audit.view_auditlog",
            "core.view_systemconfig",
            "analytics.view_kpimeasurement",
            "analytics.view_kpi",
            # Basic academic access for support
            "academics.view_class",
            "academics.view_student",
            "academics.view_teacher",
        ]

    def _get_transport_manager_permissions(self):
        """Transport manager gets full transport permissions"""
        return [
            "transport.add_vehicle",
            "transport.change_vehicle",
            "transport.delete_vehicle",
            "transport.view_vehicle",
            "transport.add_driver",
            "transport.change_driver",
            "transport.delete_driver",
            "transport.view_driver",
            "transport.add_attendant",
            "transport.change_attendant",
            "transport.delete_attendant",
            "transport.view_attendant",
            "transport.add_route",
            "transport.change_route",
            "transport.delete_route",
            "transport.view_route",
            "transport.add_routestop",
            "transport.change_routestop",
            "transport.delete_routestop",
            "transport.view_routestop",
            "transport.add_routeschedule",
            "transport.change_routeschedule",
            "transport.delete_routeschedule",
            "transport.view_routeschedule",
            "transport.add_transportallocation",
            "transport.change_transportallocation",
            "transport.delete_transportallocation",
            "transport.view_transportallocation",
            "transport.add_maintenancerecord",
            "transport.change_maintenancerecord",
            "transport.delete_maintenancerecord",
            "transport.view_maintenancerecord",
            "transport.add_fuelrecord",
            "transport.change_fuelrecord",
            "transport.delete_fuelrecord",
            "transport.view_fuelrecord",
            "transport.add_incidentreport",
            "transport.change_incidentreport",
            "transport.delete_incidentreport",
            "transport.view_incidentreport",
        ]

    def _get_activities_coordinator_permissions(self):
        """Activities Coordinator gets extracurricular activities permissions aligned with Features.md"""
        return [
            # Activities management (Features.md: Planning, Registration)
            "activities.add_activity",
            "activities.change_activity",
            "activities.delete_activity",
            "activities.view_activity",
            "activities.add_activityenrollment",
            "activities.change_activityenrollment",
            "activities.delete_activityenrollment",
            "activities.view_activityenrollment",
            "activities.add_equipment",
            "activities.change_equipment",
            "activities.delete_equipment",
            "activities.view_equipment",
            "activities.add_activitybudget",
            "activities.change_activitybudget",
            "activities.delete_activitybudget",
            "activities.view_activitybudget",
            "activities.add_competition",
            "activities.change_competition",
            "activities.delete_competition",
            "activities.view_competition",
            # Student access for registration management
            "academics.view_student",
            "academics.view_class",
            # Communication for activity coordination
            "communication.add_announcement",
            "communication.change_announcement",
            "communication.view_announcement",
            "communication.add_message",
            "communication.view_message",
        ]

    def _get_hostel_warden_permissions(self):
        """Hostel warden gets hostel permissions"""
        return [
            "hostels.add_hostel",
            "hostels.change_hostel",
            "hostels.delete_hostel",
            "hostels.view_hostel",
            "hostels.add_room",
            "hostels.change_room",
            "hostels.delete_room",
            "hostels.view_room",
            "hostels.add_bed",
            "hostels.change_bed",
            "hostels.delete_bed",
            "hostels.view_bed",
            "hostels.add_hostelallocation",
            "hostels.change_hostelallocation",
            "hostels.delete_hostelallocation",
            "hostels.view_hostelallocation",
            "hostels.add_hostelfee",
            "hostels.change_hostelfee",
            "hostels.delete_hostelfee",
            "hostels.view_hostelfee",
            "hostels.add_visitorlog",
            "hostels.change_visitorlog",
            "hostels.delete_visitorlog",
            "hostels.view_visitorlog",
            "hostels.add_maintenancerequest",
            "hostels.change_maintenancerequest",
            "hostels.delete_maintenancerequest",
            "hostels.view_maintenancerequest",
            "hostels.add_inventoryitem",
            "hostels.change_inventoryitem",
            "hostels.delete_inventoryitem",
            "hostels.view_inventoryitem",
        ]

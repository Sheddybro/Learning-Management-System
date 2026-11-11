from django.core.management.base import BaseCommand
from apps.users.models import Role


class Command(BaseCommand):
    help = 'Seed the database with default staff roles'

    def handle(self, *args, **options):
        # Define staff roles with their display names and descriptions
        # Hierarchy levels aligned with Features.md specifications
        staff_roles_data = [
            {
                'role_type': Role.RoleType.SUPER_ADMIN,
                'name': 'Super Administrator',
                'description': 'Full system access and control',
                'hierarchy_level': 100,
            },
            {
                'role_type': Role.RoleType.SCHOOL_ADMIN,
                'name': 'School Administrator',
                'description': 'School-level administrator with academic management permissions',
                'hierarchy_level': 95,
            },
            {
                'role_type': Role.RoleType.ADMIN,
                'name': 'Administrator',
                'description': 'Administrative access to school management',
                'hierarchy_level': 90,
            },
            {
                'role_type': Role.RoleType.PRINCIPAL,
                'name': 'Principal',
                'description': 'School principal with oversight of all operations',
                'hierarchy_level': 85,
            },
            {
                'role_type': Role.RoleType.DEPARTMENT_HEAD,
                'name': 'Department Head',
                'description': 'Head of an academic department',
                'hierarchy_level': 80,
            },
            {
                'role_type': Role.RoleType.COUNSELOR,
                'name': 'School Counselor',
                'description': 'Student counseling and guidance',
                'hierarchy_level': 75,
            },
            {
                'role_type': Role.RoleType.TEACHER,
                'name': 'Teacher',
                'description': 'Classroom teacher',
                'hierarchy_level': 70,
            },
            {
                'role_type': Role.RoleType.ACCOUNTANT,
                'name': 'Accountant',
                'description': 'Financial management and accounting',
                'hierarchy_level': 65,
            },
            {
                'role_type': Role.RoleType.LIBRARIAN,
                'name': 'Librarian',
                'description': 'Library management and services',
                'hierarchy_level': 60,
            },
            {
                'role_type': Role.RoleType.ACTIVITIES_COORDINATOR,
                'name': 'Activities Coordinator',
                'description': 'Management of extracurricular activities and programs',
                'hierarchy_level': 60,
            },
            {
                'role_type': Role.RoleType.TRANSPORT_MANAGER,
                'name': 'Transport Manager',
                'description': 'Management of school transportation',
                'hierarchy_level': 55,
            },
            {
                'role_type': Role.RoleType.SUPPORT,
                'name': 'Support Staff',
                'description': 'General support staff',
                'hierarchy_level': 55,
            },
            {
                'role_type': Role.RoleType.HOSTEL_WARDEN,
                'name': 'Hostel Warden',
                'description': 'Management of student hostel facilities',
                'hierarchy_level': 55,
            },
            {
                'role_type': Role.RoleType.DRIVER,
                'name': 'Driver',
                'description': 'School transport driver',
                'hierarchy_level': 50,
            },
        ]

        created_count = 0
        updated_count = 0

        for role_data in staff_roles_data:
            role, created = Role.objects.get_or_create(
                role_type=role_data['role_type'],
                defaults={
                    'name': role_data['name'],
                    'description': role_data['description'],
                    'hierarchy_level': role_data['hierarchy_level'],
                    'is_system_role': True,
                    'status': 'active',
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created role: {role.name}')
                )
            else:
                # Update existing role if needed
                updated = False
                if role.name != role_data['name']:
                    role.name = role_data['name']
                    updated = True
                if role.description != role_data['description']:
                    role.description = role_data['description']
                    updated = True
                if role.hierarchy_level != role_data['hierarchy_level']:
                    role.hierarchy_level = role_data['hierarchy_level']
                    updated = True
                if role.status != 'active':
                    role.status = 'active'
                    updated = True

                if updated:
                    role.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Updated role: {role.name}')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Staff roles seeding completed. Created: {created_count}, Updated: {updated_count}'
            )
        )

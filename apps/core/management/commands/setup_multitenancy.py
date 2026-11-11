from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.conf import settings
from apps.core.models import Institution, InstitutionUser
from apps.users.models import Role

User = get_user_model()


class Command(BaseCommand):
    """
    Management command to set up multi-tenancy for the school platform.
    This command creates a default institution and assigns existing users to it.
    """
    help = 'Set up multi-tenancy infrastructure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--institution-name',
            type=str,
            default='Default School',
            help='Name of the default institution to create'
        )
        parser.add_argument(
            '--institution-code',
            type=str,
            default='DEFAULT',
            help='Code for the default institution'
        )
        parser.add_argument(
            '--institution-domain',
            type=str,
            default=None,
            help='Domain for the institution (optional)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Setting up multi-tenancy infrastructure...')
        )

        institution_name = options['institution_name']
        institution_code = options['institution_code']
        institution_domain = options.get('institution_domain', getattr(settings, 'SITE_DOMAIN', 'localhost'))

        # Create default institution if it doesn't exist
        institution, created = Institution.objects.get_or_create(
            code=institution_code,
            defaults={
                'name': institution_name,
                'short_name': institution_name[:50],
                'website': f'https://{institution_domain}',
                'description': f'Default institution: {institution_name}',
                'institution_type': Institution.InstitutionType.HIGH_SCHOOL,
                'ownership_type': Institution.OwnershipType.PRIVATE,
                'max_students': 1000,
                'max_staff': 100,
                'timezone': 'UTC',
                'is_active': True,
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created default institution: {institution.name} ({institution.code})')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Institution already exists: {institution.name} ({institution.code})')
            )

        # Assign existing users to the default institution
        users_assigned = 0

        # First, assign superusers and staff
        staff_users = User.objects.filter(is_staff=True) | User.objects.filter(is_superuser=True)
        for user in staff_users.distinct():
            membership, membership_created = InstitutionUser.objects.get_or_create(
                user=user,
                institution=institution,
                defaults={
                    'is_primary': True,
                    'employee_id': f'STAFF_{user.id}',
                }
            )
            if membership_created:
                users_assigned += 1
                self.stdout.write(f'Assigned staff user: {user.email}')

        # Then assign regular users (if they have complete profiles)
        regular_users = User.objects.filter(
            is_staff=False,
            is_superuser=False,
            user_roles__isnull=False
        ).distinct()

        for user in regular_users:
            membership, membership_created = InstitutionUser.objects.get_or_create(
                user=user,
                institution=institution,
                defaults={
                    'is_primary': True,
                }
            )
            if membership_created:
                users_assigned += 1
                self.stdout.write(f'Assigned regular user: {user.email}')

        self.stdout.write(
            self.style.SUCCESS(f'Multi-tenancy setup complete! Users assigned: {users_assigned}')
        )

        # Display summary
        total_users = User.objects.count()
        institution_users = InstitutionUser.objects.filter(institution=institution).count()

        self.stdout.write(
            self.style.SUCCESS(f'Institution: {institution.name}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Total users in system: {total_users}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Users assigned to institution: {institution_users}')
        )

        self.stdout.write(
            self.style.SUCCESS('\nNext steps:')
        )
        self.stdout.write('- Update TENANT_DOMAIN in settings.py for production')
        self.stdout.write('- Create additional institutions as needed via admin')
        self.stdout.write('- Test tenant middleware by accessing different subdomains')
        self.stdout.write('- Update ALLOWED_HOSTS to include tenant subdomains in production')

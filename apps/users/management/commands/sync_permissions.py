from django.core.management.base import BaseCommand
from apps.users.models import User, sync_user_permissions


class Command(BaseCommand):
    help = 'Sync permissions for all users based on their roles'

    def handle(self, *args, **options):
        self.stdout.write('Syncing permissions for all users...\n')

        users = User.objects.all()
        total_synced = 0

        for user in users:
            try:
                count = sync_user_permissions(user)
                if count > 0:
                    total_synced += 1
                    self.stdout.write(f'Synced {count} permissions for {user.email}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error syncing permissions for {user.email}: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Permissions synced for {total_synced} users')
        )

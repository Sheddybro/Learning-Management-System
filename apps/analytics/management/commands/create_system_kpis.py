from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _
from apps.analytics.models import KPI
from apps.academics.models import AcademicSession


class Command(BaseCommand):
    help = 'Create system performance KPIs for monitoring'

    def handle(self, *args, **options):
        # Note: No longer creating default academic session
        # KPIs can function without sessions and measurements will be tied to sessions when they exist

        # System Performance KPIs
        system_kpis = [
            {
                'name': 'CPU Usage',
                'code': 'system_cpu_usage',
                'category': 'system',
                'description': 'Percentage of CPU utilization across the system',
                'value_type': 'percentage',
                'target_value': 70.0,
                'max_value': 100.0,
                'refresh_frequency': 'realtime',
                'is_trending': True,
                'display_format': '{value}%',
                'data_source': 'system.monitoring.cpu',
            },
            {
                'name': 'Memory Usage',
                'code': 'system_memory_usage',
                'category': 'system',
                'description': 'Percentage of RAM memory utilization',
                'value_type': 'percentage',
                'target_value': 80.0,
                'max_value': 100.0,
                'refresh_frequency': 'realtime',
                'is_trending': True,
                'display_format': '{value}%',
                'data_source': 'system.monitoring.memory',
            },
            {
                'name': 'Disk Usage',
                'code': 'system_disk_usage',
                'category': 'system',
                'description': 'Percentage of disk storage utilization',
                'value_type': 'percentage',
                'target_value': 85.0,
                'max_value': 100.0,
                'refresh_frequency': 'hourly',
                'is_trending': True,
                'display_format': '{value}%',
                'data_source': 'system.monitoring.disk',
            },
            {
                'name': 'Database Connections',
                'code': 'db_active_connections',
                'category': 'system',
                'description': 'Number of active database connections',
                'value_type': 'number',
                'target_value': 50.0,
                'max_value': 100.0,
                'refresh_frequency': 'realtime',
                'is_trending': True,
                'display_format': '{value}',
                'data_source': 'database.monitoring.connections',
            },
            {
                'name': 'Average Response Time',
                'code': 'app_response_time',
                'category': 'system',
                'description': 'Average application response time in milliseconds',
                'value_type': 'duration',
                'target_value': 500.0,  # 500ms target
                'max_value': 2000.0,   # 2s max acceptable
                'refresh_frequency': 'realtime',
                'is_trending': True,
                'display_format': '{value}ms',
                'data_source': 'application.monitoring.response_time',
            },
            {
                'name': 'Error Rate',
                'code': 'app_error_rate',
                'category': 'system',
                'description': 'Percentage of requests resulting in errors',
                'value_type': 'percentage',
                'target_value': 1.0,   # 1% target
                'max_value': 5.0,     # 5% max acceptable
                'refresh_frequency': 'hourly',
                'is_trending': True,
                'display_format': '{value}%',
                'data_source': 'application.monitoring.errors',
            },
            {
                'name': 'Active User Sessions',
                'code': 'user_active_sessions',
                'category': 'system',
                'description': 'Number of currently active user sessions',
                'value_type': 'number',
                'target_value': 1000.0,
                'refresh_frequency': 'realtime',
                'is_trending': True,
                'display_format': '{value}',
                'data_source': 'users.monitoring.sessions',
            },
            {
                'name': 'Database Query Performance',
                'code': 'db_query_performance',
                'category': 'system',
                'description': 'Average database query execution time in milliseconds',
                'value_type': 'duration',
                'target_value': 100.0,  # 100ms target
                'max_value': 1000.0,   # 1s max acceptable
                'refresh_frequency': 'hourly',
                'is_trending': True,
                'display_format': '{value}ms',
                'data_source': 'database.monitoring.query_time',
            },
            {
                'name': 'System Uptime',
                'code': 'system_uptime',
                'category': 'system',
                'description': 'System uptime percentage over the last 30 days',
                'value_type': 'percentage',
                'target_value': 99.9,
                'refresh_frequency': 'daily',
                'is_trending': True,
                'display_format': '{value}%',
                'data_source': 'system.monitoring.uptime',
            },
            {
                'name': 'Backup Status',
                'code': 'backup_status',
                'category': 'system',
                'description': 'Days since last successful backup',
                'value_type': 'number',
                'target_value': 1.0,   # Daily backup target
                'max_value': 7.0,     # Max 7 days acceptable
                'refresh_frequency': 'daily',
                'is_trending': False,
                'display_format': '{value} days',
                'data_source': 'system.monitoring.backup',
            },
        ]

        created_count = 0
        updated_count = 0

        for kpi_data in system_kpis:
            kpi, created = KPI.objects.get_or_create(
                code=kpi_data['code'],
                defaults=kpi_data
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created KPI: {kpi.name}')
                )
            else:
                # Update existing KPI with new values
                for key, value in kpi_data.items():
                    setattr(kpi, key, value)
                kpi.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated KPI: {kpi.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'System KPIs setup complete. Created: {created_count}, Updated: {updated_count}'
            )
        )

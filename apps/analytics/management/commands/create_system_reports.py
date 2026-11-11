from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _
from apps.analytics.models import ReportType


class Command(BaseCommand):
    help = 'Create system performance report types'

    def handle(self, *args, **options):
        # System Performance Report Types
        system_reports = [
            {
                'name': 'System Performance Report',
                'code': 'system_performance_report',
                'category': 'system',
                'description': 'Comprehensive system performance metrics and trends',
                'data_source': 'system.monitoring.all',
                'is_standard': True,
                'parameters_schema': {
                    'type': 'object',
                    'properties': {
                        'date_range': {
                            'type': 'string',
                            'title': 'Date Range',
                            'enum': ['last_24h', 'last_7d', 'last_30d', 'custom'],
                            'default': 'last_7d'
                        },
                        'start_date': {
                            'type': 'string',
                            'format': 'date',
                            'title': 'Start Date'
                        },
                        'end_date': {
                            'type': 'string',
                            'format': 'date',
                            'title': 'End Date'
                        },
                        'include_trends': {
                            'type': 'boolean',
                            'title': 'Include Trend Analysis',
                            'default': True
                        }
                    },
                    'required': []
                },
                'refresh_frequency': 'daily',
                'access_roles': ['super_admin', 'admin'],
            },
            {
                'name': 'Capacity Planning Report',
                'code': 'capacity_planning_report',
                'category': 'system',
                'description': 'Capacity planning analysis based on system usage trends',
                'data_source': 'system.capacity.planning',
                'is_standard': True,
                'parameters_schema': {
                    'type': 'object',
                    'properties': {
                        'projection_period': {
                            'type': 'integer',
                            'title': 'Projection Period (months)',
                            'minimum': 1,
                            'maximum': 24,
                            'default': 6
                        },
                        'growth_rate': {
                            'type': 'number',
                            'title': 'Expected Growth Rate (%)',
                            'minimum': 0,
                            'maximum': 100,
                            'default': 10
                        },
                        'include_recommendations': {
                            'type': 'boolean',
                            'title': 'Include Recommendations',
                            'default': True
                        }
                    },
                    'required': []
                },
                'refresh_frequency': 'weekly',
                'access_roles': ['super_admin', 'admin'],
            },
            {
                'name': 'System Health Check',
                'code': 'system_health_check',
                'category': 'system',
                'description': 'System health status and alerts summary',
                'data_source': 'system.health.status',
                'is_standard': True,
                'parameters_schema': {
                    'type': 'object',
                    'properties': {
                        'check_type': {
                            'type': 'string',
                            'title': 'Check Type',
                            'enum': ['full', 'quick', 'custom'],
                            'default': 'full'
                        },
                        'include_alerts': {
                            'type': 'boolean',
                            'title': 'Include Active Alerts',
                            'default': True
                        }
                    },
                    'required': []
                },
                'refresh_frequency': 'hourly',
                'access_roles': ['super_admin', 'admin', 'support'],
            },
        ]

        created_count = 0
        updated_count = 0

        for report_data in system_reports:
            report_type, created = ReportType.objects.get_or_create(
                code=report_data['code'],
                defaults=report_data
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created Report Type: {report_type.name}')
                )
            else:
                # Update existing report type with new values
                for key, value in report_data.items():
                    setattr(report_type, key, value)
                report_type.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated Report Type: {report_type.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'System report types setup complete. Created: {created_count}, Updated: {updated_count}'
            )
        )

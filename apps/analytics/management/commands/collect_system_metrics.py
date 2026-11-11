import psutil
import os
import time
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import connection
from apps.analytics.models import KPI, KPIMeasurement
from apps.academics.models import AcademicSession
from apps.users.models import User


class Command(BaseCommand):
    help = 'Collect system performance metrics and update KPIs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be collected without saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be saved'))

        # Get current academic session
        try:
            current_session = AcademicSession.objects.filter(status='active').first()
            if not current_session:
                self.stdout.write(self.style.ERROR('No active academic session found'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting academic session: {e}'))
            return

        # Collect system metrics
        metrics = self.collect_system_metrics()

        if dry_run:
            self.display_metrics(metrics)
            return

        # Save measurements
        saved_count = 0
        for metric_code, value in metrics.items():
            try:
                kpi = KPI.objects.get(code=metric_code, status='active')
                measurement = KPIMeasurement.objects.create(
                    kpi=kpi,
                    academic_session=current_session,
                    measured_at=timezone.now(),
                    value=value,
                )
                saved_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Saved {kpi.name}: {value} {kpi.display_format.replace("{value}", "")}')
                )
            except KPI.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'KPI {metric_code} not found, skipping')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error saving {metric_code}: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'System metrics collection complete. Saved {saved_count} measurements.')
        )

    def collect_system_metrics(self):
        """Collect various system performance metrics."""
        metrics = {}

        try:
            # CPU Usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics['system_cpu_usage'] = round(cpu_percent, 2)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'CPU collection error: {e}'))
            metrics['system_cpu_usage'] = 0.0

        try:
            # Memory Usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            metrics['system_memory_usage'] = round(memory_percent, 2)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Memory collection error: {e}'))
            metrics['system_memory_usage'] = 0.0

        try:
            # Disk Usage (system drive)
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            metrics['system_disk_usage'] = round(disk_percent, 2)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Disk collection error: {e}'))
            metrics['system_disk_usage'] = 0.0

        try:
            # Database Connections (simplified - count active connections)
            # This is a basic implementation - in production you'd use database-specific tools
            with connection.cursor() as cursor:
                if 'sqlite' in connection.vendor:
                    # SQLite doesn't have connection count query
                    metrics['db_active_connections'] = 1  # Placeholder
                else:
                    # For PostgreSQL/MySQL
                    cursor.execute("SELECT COUNT(*) FROM pg_stat_activity;" if 'postgres' in connection.vendor else "SHOW PROCESSLIST;")
                    result = cursor.fetchone()
                    metrics['db_active_connections'] = result[0] if result else 1
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Database connections error: {e}'))
            metrics['db_active_connections'] = 1

        try:
            # Application Response Time (simplified - using a basic request simulation)
            # In production, this would be collected from actual request logs
            metrics['app_response_time'] = 250.0  # Placeholder - would be calculated from logs
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Response time error: {e}'))
            metrics['app_response_time'] = 500.0

        try:
            # Error Rate (simplified - would be calculated from error logs)
            metrics['app_error_rate'] = 0.5  # Placeholder - 0.5% error rate
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Error rate error: {e}'))
            metrics['app_error_rate'] = 1.0

        try:
            # Active User Sessions
            # Count users who have been active in the last 30 minutes
            thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
            active_sessions = User.objects.filter(
                last_login__gte=thirty_minutes_ago,
                is_active=True
            ).count()
            metrics['user_active_sessions'] = active_sessions
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Active sessions error: {e}'))
            metrics['user_active_sessions'] = 0

        try:
            # Database Query Performance (simplified - average query time)
            # In production, this would analyze query logs
            metrics['db_query_performance'] = 50.0  # Placeholder - 50ms average
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Query performance error: {e}'))
            metrics['db_query_performance'] = 100.0

        try:
            # System Uptime (percentage over last 30 days)
            # Calculate based on system boot time
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            uptime_days = uptime_seconds / (24 * 60 * 60)
            uptime_percentage = min((uptime_days / 30) * 100, 100)  # Max 100%
            metrics['system_uptime'] = round(uptime_percentage, 2)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Uptime error: {e}'))
            metrics['system_uptime'] = 99.9

        try:
            # Backup Status (days since last backup)
            # This would typically check backup logs or file timestamps
            metrics['backup_status'] = 1  # Placeholder - 1 day since last backup
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Backup status error: {e}'))
            metrics['backup_status'] = 7

        return metrics

    def display_metrics(self, metrics):
        """Display collected metrics in dry-run mode."""
        self.stdout.write(self.style.SUCCESS('\nCollected System Metrics (DRY RUN):'))
        self.stdout.write('=' * 50)

        for code, value in metrics.items():
            try:
                kpi = KPI.objects.get(code=code, status='active')
                display_value = kpi.display_format.replace('{value}', str(value))
                self.stdout.write(f'{kpi.name}: {display_value}')
            except KPI.DoesNotExist:
                self.stdout.write(f'{code}: {value} (KPI not found)')

        self.stdout.write('=' * 50)

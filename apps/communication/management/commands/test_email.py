"""
Management command to test email functionality.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone

from apps.communication.services import EmailService, EmailTemplateService
from apps.communication.models import EmailTemplate


class Command(BaseCommand):
    help = 'Test email functionality and configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address to send test email to (defaults to DEFAULT_FROM_EMAIL)',
        )
        parser.add_argument(
            '--template',
            type=str,
            help='Name of email template to test',
        )
        parser.add_argument(
            '--connection-only',
            action='store_true',
            help='Only test email connection, do not send test email',
        )
        parser.add_argument(
            '--create-templates',
            action='store_true',
            help='Create basic email templates if they do not exist',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Testing Email Configuration')
        )
        self.stdout.write('=' * 50)

        # Test email connection
        self.stdout.write('1. Testing email connection...')
        success, message = EmailService.test_email_connection()

        if success:
            self.stdout.write(
                self.style.SUCCESS(f'   ✓ {message}')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'   ✗ {message}')
            )
            return

        if options['connection_only']:
            return

        # Get test email address
        test_email = options.get('email') or settings.DEFAULT_FROM_EMAIL
        self.stdout.write(f'2. Test email address: {test_email}')

        # Create basic templates if requested
        if options['create_templates']:
            self.create_basic_templates()

        # Test template-based email
        template_name = options.get('template')
        if template_name:
            self.test_template_email(template_name, test_email)
        else:
            self.test_basic_email(test_email)

        self.stdout.write(
            self.style.SUCCESS('\nEmail testing completed!')
        )

    def create_basic_templates(self):
        """Create basic email templates for testing."""
        self.stdout.write('3. Creating basic email templates...')

        templates_data = [
            {
                'name': 'test_email',
                'subject': 'Test Email from {{ site_name }}',
                'html_content': '''
                <html>
                <body>
                    <h1>Test Email</h1>
                    <p>Hello {{ recipient_name }}!</p>
                    <p>This is a test email sent from {{ site_name }} at {{ current_time }}.</p>
                    <p>If you received this email, your email configuration is working correctly!</p>
                    <br>
                    <p>Best regards,<br>{{ site_name }} Team</p>
                </body>
                </html>
                ''',
                'text_content': '''
                Test Email

                Hello {{ recipient_name }}!

                This is a test email sent from {{ site_name }} at {{ current_time }}.

                If you received this email, your email configuration is working correctly!

                Best regards,
                {{ site_name }} Team
                ''',
                'variables': {
                    'site_name': 'School Management System',
                    'recipient_name': 'Test User',
                    'current_time': str(timezone.now())
                }
            },
            {
                'name': 'welcome_email',
                'subject': 'Welcome to {{ site_name }}!',
                'html_content': '''
                <html>
                <body>
                    <h1>Welcome to {{ site_name }}!</h1>
                    <p>Dear {{ user_name }},</p>
                    <p>Welcome to our school management system! Your account has been successfully created.</p>
                    <p>You can now:</p>
                    <ul>
                        <li>Access your dashboard</li>
                        <li>View announcements</li>
                        <li>Manage your profile</li>
                    </ul>
                    <p>If you have any questions, please don't hesitate to contact us.</p>
                    <br>
                    <p>Best regards,<br>{{ site_name }} Team</p>
                </body>
                </html>
                ''',
                'text_content': '''
                Welcome to {{ site_name }}!

                Dear {{ user_name }},

                Welcome to our school management system! Your account has been successfully created.

                You can now:
                - Access your dashboard
                - View announcements
                - Manage your profile

                If you have any questions, please don't hesitate to contact us.

                Best regards,
                {{ site_name }} Team
                ''',
                'variables': {
                    'site_name': 'School Management System',
                    'user_name': 'New User'
                }
            }
        ]

        for template_data in templates_data:
            template, created = EmailTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults={
                    'template_type': EmailTemplate.TemplateType.SYSTEM,
                    'subject': template_data['subject'],
                    'body_html': template_data['html_content'],
                    'body_text': template_data['text_content'],
                    'language': 'en',
                    'variables': template_data['variables'],
                    'is_active': True,
                }
            )

            if created:
                self.stdout.write(f'   ✓ Created template: {template.name}')
            else:
                self.stdout.write(f'   - Template already exists: {template.name}')

    def test_basic_email(self, test_email):
        """Send a basic test email."""
        self.stdout.write('3. Sending basic test email...')

        subject = f"Email Test - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        html_content = f"""
        <html>
        <body>
            <h1>Email Configuration Test</h1>
            <p>This is a test email to verify your Gmail SMTP configuration is working.</p>
            <p><strong>Test Details:</strong></p>
            <ul>
                <li>Time: {timezone.now()}</li>
                <li>From: {settings.DEFAULT_FROM_EMAIL}</li>
                <li>Backend: {settings.EMAIL_BACKEND}</li>
                <li>Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}</li>
                <li>TLS: {settings.EMAIL_USE_TLS}</li>
            </ul>
            <p>If you received this email, your email configuration is working correctly!</p>
        </body>
        </html>
        """

        success, message, sent_email = EmailService.send_email(
            recipient_email=test_email,
            subject=subject,
            html_content=html_content,
        )

        if success:
            self.stdout.write(
                self.style.SUCCESS(f'   ✓ {message}')
            )
            if sent_email:
                self.stdout.write(f'   - Email ID: {sent_email.id}')
        else:
            self.stdout.write(
                self.style.ERROR(f'   ✗ {message}')
            )

    def test_template_email(self, template_name, test_email):
        """Send a test email using a template."""
        self.stdout.write(f'3. Testing template: {template_name}')

        template = EmailTemplateService.get_template_by_name(template_name)
        if not template:
            raise CommandError(f'Template "{template_name}" not found or not active.')

        # Prepare test context
        context = {
            'site_name': 'School Management System',
            'recipient_name': 'Test User',
            'user_name': 'Test User',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        success, message, sent_email = EmailService.send_templated_email(
            template=template,
            recipient_email=test_email,
            context=context,
        )

        if success:
            self.stdout.write(
                self.style.SUCCESS(f'   ✓ {message}')
            )
            if sent_email:
                self.stdout.write(f'   - Email ID: {sent_email.id}')
                self.stdout.write(f'   - Template: {template.name}')
        else:
            self.stdout.write(
                self.style.ERROR(f'   ✗ {message}')
            )

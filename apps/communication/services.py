"""
Email services for the communication app.
Provides utilities for sending emails using templates and tracking sent emails.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template import Template, Context
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import EmailTemplate, SentEmail

logger = logging.getLogger(__name__)
User = get_user_model()


class EmailService:
    """
    Service class for handling email operations.
    """

    @staticmethod
    def send_email(
        recipient_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        recipient_user: Optional[User] = None,
        sender_user: Optional[User] = None,
        template: Optional[EmailTemplate] = None,
        context: Optional[Dict] = None,
        attachments: Optional[List] = None,
    ) -> Tuple[bool, str, Optional[SentEmail]]:
        """
        Send an email and track it in the database.

        Args:
            recipient_email: Email address of the recipient
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text content (optional)
            from_email: Sender email address (defaults to DEFAULT_FROM_EMAIL)
            recipient_user: User object of the recipient (optional)
            sender_user: User object of the sender (optional)
            template: EmailTemplate instance used (optional)
            context: Template context used (optional)
            attachments: List of attachments (optional)

        Returns:
            Tuple of (success: bool, message: str, sent_email: SentEmail or None)
        """
        try:
            from_email = from_email or settings.DEFAULT_FROM_EMAIL

            # Create the email message
            if text_content:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=from_email,
                    to=[recipient_email]
                )
                email.attach_alternative(html_content, "text/html")
            else:
                email = send_mail(
                    subject=subject,
                    message=html_content,
                    from_email=from_email,
                    recipient_list=[recipient_email],
                    html_message=html_content
                )

            # Add attachments if provided
            if attachments and hasattr(email, 'attach'):
                for attachment in attachments:
                    if isinstance(attachment, tuple):
                        email.attach(*attachment)
                    else:
                        email.attach(attachment)

            # Send the email
            if hasattr(email, 'send'):
                result = email.send()
            else:
                result = email  # send_mail returns the number of sent emails

            if result > 0:
                # Track the sent email
                sent_email = SentEmail.objects.create(
                    template=template,
                    sender=sender_user,
                    recipient_email=recipient_email,
                    recipient_user=recipient_user,
                    subject=subject,
                    body_html=html_content,
                    body_text=text_content or "",
                    sent_at=timezone.now(),
                    message_id=getattr(email, 'message_id', '') if hasattr(email, 'message_id') else '',
                )

                logger.info(f"Email sent successfully to {recipient_email}")
                return True, "Email sent successfully", sent_email
            else:
                logger.error(f"Failed to send email to {recipient_email}")
                return False, "Failed to send email", None

        except Exception as e:
            error_msg = f"Error sending email to {recipient_email}: {str(e)}"
            logger.error(error_msg)

            # Still track failed emails for debugging
            try:
                SentEmail.objects.create(
                    template=template,
                    sender=sender_user,
                    recipient_email=recipient_email,
                    recipient_user=recipient_user,
                    subject=subject,
                    body_html=html_content,
                    body_text=text_content or "",
                    sent_at=timezone.now(),
                    error_message=str(e),
                )
            except Exception as db_error:
                logger.error(f"Failed to track email error in database: {str(db_error)}")

            return False, error_msg, None

    @staticmethod
    def send_templated_email(
        template: EmailTemplate,
        recipient_email: str,
        context: Dict,
        recipient_user: Optional[User] = None,
        sender_user: Optional[User] = None,
        from_email: Optional[str] = None,
        attachments: Optional[List] = None,
    ) -> Tuple[bool, str, Optional[SentEmail]]:
        """
        Send an email using an EmailTemplate.

        Args:
            template: EmailTemplate instance to use
            recipient_email: Email address of the recipient
            context: Context dictionary for template rendering
            recipient_user: User object of the recipient (optional)
            sender_user: User object of the sender (optional)
            from_email: Sender email address (optional)
            attachments: List of attachments (optional)

        Returns:
            Tuple of (success: bool, message: str, sent_email: SentEmail or None)
        """
        if not template.is_active:
            return False, "Email template is not active", None

        try:
            # Render subject and content
            subject, html_content, text_content = template.render_template(context)

            return EmailService.send_email(
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                from_email=from_email,
                recipient_user=recipient_user,
                sender_user=sender_user,
                template=template,
                context=context,
                attachments=attachments,
            )

        except Exception as e:
            error_msg = f"Error rendering template {template.name}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    @staticmethod
    def send_bulk_email(
        template: EmailTemplate,
        recipients: List[Dict],
        context: Dict,
        sender_user: Optional[User] = None,
        from_email: Optional[str] = None,
    ) -> Dict[str, Union[int, List[Dict]]]:
        """
        Send bulk emails using a template.

        Args:
            template: EmailTemplate instance to use
            recipients: List of dicts with 'email' and optional 'user' keys
            context: Base context dictionary (will be merged with recipient-specific context)
            sender_user: User object of the sender (optional)
            from_email: Sender email address (optional)

        Returns:
            Dict with 'total', 'successful', 'failed', and 'results' keys
        """
        total = len(recipients)
        successful = 0
        failed = 0
        results = []

        for recipient_data in recipients:
            recipient_email = recipient_data.get('email')
            recipient_user = recipient_data.get('user')
            recipient_context = recipient_data.get('context', {})

            # Merge contexts
            merged_context = {**context, **recipient_context}

            success, message, sent_email = EmailService.send_templated_email(
                template=template,
                recipient_email=recipient_email,
                context=merged_context,
                recipient_user=recipient_user,
                sender_user=sender_user,
                from_email=from_email,
            )

            if success:
                successful += 1
            else:
                failed += 1

            results.append({
                'email': recipient_email,
                'success': success,
                'message': message,
                'sent_email_id': sent_email.id if sent_email else None,
            })

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'results': results,
        }

    @staticmethod
    def test_email_connection() -> Tuple[bool, str]:
        """
        Test the email connection configuration.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            from django.core.mail import get_connection
            connection = get_connection()
            connection.open()
            connection.close()
            return True, "Email connection test successful"
        except Exception as e:
            return False, f"Email connection test failed: {str(e)}"


class EmailTemplateService:
    """
    Service class for managing email templates.
    """

    @staticmethod
    def create_template(
        name: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        template_type: str = EmailTemplate.TemplateType.SYSTEM,
        language: str = 'en',
        variables: Optional[Dict] = None,
    ) -> EmailTemplate:
        """
        Create a new email template.

        Args:
            name: Template name
            subject: Email subject template
            html_content: HTML content template
            text_content: Plain text content template (optional)
            template_type: Type of template
            language: Language code
            variables: Available template variables

        Returns:
            Created EmailTemplate instance
        """
        return EmailTemplate.objects.create(
            name=name,
            template_type=template_type,
            subject=subject,
            body_html=html_content,
            body_text=text_content or "",
            language=language,
            variables=variables or {},
        )

    @staticmethod
    def get_template_by_name(name: str, language: str = 'en') -> Optional[EmailTemplate]:
        """
        Get an active email template by name and language.

        Args:
            name: Template name
            language: Language code

        Returns:
            EmailTemplate instance or None
        """
        try:
            return EmailTemplate.objects.get(
                name=name,
                language=language,
                is_active=True
            )
        except EmailTemplate.DoesNotExist:
            return None

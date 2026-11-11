from django.core.management.base import BaseCommand
from apps.support.models import LegalDocument


class Command(BaseCommand):
    help = 'Populate the database with initial legal documents for the support system'

    def handle(self, *args, **options):
        # Define the legal documents data
        documents_data = [
            {
                'document_type': 'terms_of_service',
                'title': 'Terms of Service',
                'slug': 'terms-of-service',
                'content': '''
# Terms of Service for Nexus School Management System

## 1. Acceptance of Terms

By accessing and using the Nexus School Management System ("the System"), you accept and agree to be bound by the terms and provision of this agreement.

## 2. Use License

Permission is granted to temporarily download one copy of the System per user for personal, non-commercial transitory viewing only.

## 3. Disclaimer

The materials on the System are provided on an 'as is' basis. The School makes no warranties, expressed or implied, and hereby disclaims and negates all other warranties.

## 4. Limitations

In no event shall the School or its suppliers be liable for any damages (including, without limitation, damages for loss of data or profit).

## 5. Accuracy of Materials

The materials appearing on the System could include technical, typographical, or photographic errors. The School does not warrant that any of the materials on its System are accurate, complete, or current.

## 6. Modifications

The School may revise these terms of service at any time without notice. By using this System you are agreeing to be bound by the then current version of these Terms and Conditions of Use.

## 7. Data Privacy

Your privacy is important to us. Please review our Privacy Policy, which also governs your use of the System, to understand our practices.
                ''',
                'is_active': True,
                'requires_acknowledgment': True
            },
            {
                'document_type': 'privacy_policy',
                'title': 'Privacy Policy',
                'slug': 'privacy-policy',
                'content': '''
# Privacy Policy for Nexus School Management System

## 1. Information We Collect

We collect information you provide directly to us, such as when you create an account, use our services, or contact us for support.

## 2. How We Use Your Information

We use the information we collect to:
- Provide, maintain, and improve our services
- Process transactions and send related information
- Send you technical notices, updates, and support messages
- Respond to your comments and questions

## 3. Information Sharing

We do not sell, trade, or otherwise transfer your personal information to third parties without your consent, except as described in this policy.

## 4. Data Security

We implement appropriate technical and organizational measures to protect your personal information against unauthorized access, alteration, disclosure, or destruction.

## 5. Changes to This Policy

We may update this privacy policy from time to time. We will notify you of any changes by posting the new policy on this page.
                ''',
                'is_active': True,
                'requires_acknowledgment': False
            },
            {
                'document_type': 'cookie_policy',
                'title': 'Cookie Policy',
                'slug': 'cookie-policy',
                'content': '''
# Cookie Policy for Nexus School Management System

## What Are Cookies

Cookies are small text files that are placed on your computer or mobile device when you visit our website.

## How We Use Cookies

We use cookies to:
- Remember your preferences and settings
- Keep you signed in to your account
- Analyze how our site is used
- Improve our services

## Types of Cookies We Use

### Essential Cookies
Required for the website to function properly.

### Analytics Cookies
Help us understand how visitors interact with our website.

### Preference Cookies
Remember your settings and preferences.

## Managing Cookies

You can control cookies through your browser settings. However, disabling cookies may affect the functionality of our website.
                ''',
                'is_active': True,
                'requires_acknowledgment': False
            },
            {
                'document_type': 'data_protection',
                'title': 'Data Protection Policy',
                'slug': 'data-protection',
                'content': '''
# Data Protection Policy for Nexus School Management System

## 1. Introduction

This policy outlines how we handle personal data in compliance with applicable data protection laws.

## 2. Data Collection Principles

We collect and process personal data fairly, lawfully, and transparently.

## 3. Data Subject Rights

You have the right to:
- Access your personal data
- Rectify inaccurate data
- Erase your data ("right to be forgotten")
- Restrict processing
- Data portability
- Object to processing

## 4. Data Security

We implement appropriate security measures to protect personal data against unauthorized access, loss, or damage.

## 5. Data Retention

We retain personal data only as long as necessary for the purposes for which it was collected.
                ''',
                'is_active': True,
                'requires_acknowledgment': False
            },
            {
                'document_type': 'accessibility_statement',
                'title': 'Accessibility Statement',
                'slug': 'accessibility-statement',
                'content': '''
# Accessibility Statement for Nexus School Management System

## Our Commitment

We are committed to ensuring digital accessibility for people with disabilities. We are continually improving the user experience for everyone.

## Compliance Standards

Our website aims to conform to Web Content Accessibility Guidelines (WCAG) 2.1 AA standards.

## Accessibility Features

- Keyboard navigation support
- Screen reader compatibility
- High contrast options
- Resizable text
- Alternative text for images

## Feedback

If you encounter accessibility barriers, please contact us at accessibility@nexus-sms.edu or through our support system.

## Contact Information

For questions about this accessibility statement, please contact:
Accessibility Team
Nexus School Management System
Email: accessibility@nexus-sms.edu
                ''',
                'is_active': True,
                'requires_acknowledgment': False
            }
        ]

        created_count = 0
        updated_count = 0

        for doc_data in documents_data:
            # Check if document already exists
            existing_doc = LegalDocument.objects.filter(
                document_type=doc_data['document_type']
            ).first()

            if existing_doc:
                # Update content if needed
                if existing_doc.title != doc_data['title'] or existing_doc.content.strip() != doc_data['content'].strip():
                    existing_doc.title = doc_data['title']
                    existing_doc.content = doc_data['content'].strip()
                    existing_doc.slug = doc_data['slug']
                    existing_doc.is_active = doc_data['is_active']
                    existing_doc.requires_acknowledgment = doc_data['requires_acknowledgment']
                    existing_doc.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Updated document: {doc_data["title"]}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Document already exists: {doc_data["title"]}')
                    )
            else:
                # Create new document
                LegalDocument.objects.create(
                    document_type=doc_data['document_type'],
                    title=doc_data['title'],
                    slug=doc_data['slug'],
                    content=doc_data['content'].strip(),
                    is_active=doc_data['is_active'],
                    requires_acknowledgment=doc_data['requires_acknowledgment']
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created document: {doc_data["title"]}')
                )

        if created_count > 0 or updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {created_count} and updated {updated_count} legal documents.')
            )
            self.stdout.write(
                self.style.SUCCESS('You can now view the legal documents at /support/legal-documents/')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('All legal documents already exist and are up to date.')
            )

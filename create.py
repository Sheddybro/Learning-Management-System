#!/usr/bin/env python
"""
Consolidated System Creation Script

This script consolidates all school management system creation and setup functions
into a single executable file. It combines role creation, permission assignment,
multi-tenancy setup, analytics setup, and other initialization tasks.

Usage:
    python create.py

Features:
    - Automatically runs makemigrations and migrate
    - Executes all populate/seed management commands
    - Prompts for superuser creation
    - Comprehensive error handling and logging

Requirements:
    - Django environment must be properly configured
    - Database should be set up and available
    - All required apps must be installed

Author: Nexus Intelligence School Management System
"""

import os
import sys
import getpass
import django
from django.conf import settings
from django.core.management import call_command, execute_from_command_line
from django.contrib.auth import get_user_model
from pathlib import Path
import subprocess
import time
import re

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

User = get_user_model()


class SystemCreator:
    """Handles all system creation and setup tasks."""

    def __init__(self):
        self.created = 0
        self.updated = 0
        self.success_commands = []
        self.failed_commands = []

    def log_success(self, message):
        """Log a success message."""
        print(f"✓ {message}")

    def log_info(self, message):
        """Log an info message."""
        print(f"ℹ {message}")

    def log_warning(self, message):
        """Log a warning message."""
        print(f"⚠ {message}")

    def log_error(self, message):
        """Log an error message."""
        print(f"✗ {message}")

    def run_command(self, command_name, *args, **kwargs):
        """Run a Django management command with error handling."""
        try:
            self.log_info(f"Running {command_name}...")
            call_command(command_name, *args, **kwargs)
            self.log_success(f"Successfully executed {command_name}")
            self.success_commands.append(command_name)
            return True
        except Exception as e:
            self.log_error(f"Failed to execute {command_name}: {e}")
            self.failed_commands.append((command_name, str(e)))
            return False

    def run_migrations(self):
        """Run makemigrations and migrate."""
        self.log_info("Running database migrations...")

        # Run makemigrations for all apps
        try:
            self.run_command("makemigrations")
        except SystemExit:
            self.log_info("No changes detected or makemigrations exited normally")
        except Exception as e:
            self.log_error(f"Error running makemigrations: {e}")
            return False

        # Run migrate
        if self.run_command("migrate"):
            self.log_success("Database migrations completed successfully")
            return True
        else:
            self.log_error("Database migrations failed")
            return False

    def fix_seed_staff_roles(self):
        """Fix the seed_staff_roles command by running it after institution is created."""
        if self.fixed_seed_staff_roles:
            return True

        self.log_info("Fixing seed_staff_roles command...")
        try:
            # First, create a default institution if it doesn't exist
            from apps.core.models import Institution
            from apps.users.models import Role

            # Check if default institution exists
            default_institution = Institution.objects.filter(code="DEFAULT").first()
            if not default_institution:
                self.log_info("Creating default institution...")
                default_institution = Institution.objects.create(
                    name="Default School",
                    code="DEFAULT",
                    short_name="Default",
                    description="Default institution",
                    institution_type="high_school",
                    ownership_type="private",
                    is_active=True,
                    allows_online_enrollment=True,
                    requires_parent_approval=True,
                )
                self.log_success(
                    f"Created default institution: {default_institution.name}"
                )

            # Now run the seed_staff_roles command again
            self.log_info("Running seed_staff_roles again...")
            from apps.users.models import Role as UserRole
            from django.db import transaction

            with transaction.atomic():
                # Define staff roles with their display names and descriptions
                # Hierarchy levels aligned with Features.md specifications
                staff_roles_data = [
                    {
                        "role_type": UserRole.RoleType.SUPER_ADMIN,
                        "name": "Super Administrator",
                        "description": "Full system access and control",
                        "hierarchy_level": 100,
                    },
                    {
                        "role_type": UserRole.RoleType.SCHOOL_ADMIN,
                        "name": "School Administrator",
                        "description": "School-level administrator with comprehensive management permissions",
                        "hierarchy_level": 95,
                    },
                    {
                        "role_type": UserRole.RoleType.ADMIN,
                        "name": "Administrator",
                        "description": "Administrative access to school management",
                        "hierarchy_level": 90,
                    },
                    {
                        "role_type": UserRole.RoleType.PRINCIPAL,
                        "name": "Principal",
                        "description": "School principal with oversight of all operations",
                        "hierarchy_level": 85,
                    },
                    {
                        "role_type": UserRole.RoleType.DEPARTMENT_HEAD,
                        "name": "Department Head",
                        "description": "Head of an academic department",
                        "hierarchy_level": 80,
                    },
                    {
                        "role_type": UserRole.RoleType.COUNSELOR,
                        "name": "School Counselor",
                        "description": "Student counseling and guidance",
                        "hierarchy_level": 75,
                    },
                    {
                        "role_type": UserRole.RoleType.TEACHER,
                        "name": "Teacher",
                        "description": "Classroom teacher",
                        "hierarchy_level": 70,
                    },
                    {
                        "role_type": UserRole.RoleType.ACCOUNTANT,
                        "name": "Accountant",
                        "description": "Financial management and accounting",
                        "hierarchy_level": 65,
                    },
                    {
                        "role_type": UserRole.RoleType.LIBRARIAN,
                        "name": "Librarian",
                        "description": "Library management and services",
                        "hierarchy_level": 60,
                    },
                    {
                        "role_type": UserRole.RoleType.ACTIVITIES_COORDINATOR,
                        "name": "Activities Coordinator",
                        "description": "Management of extracurricular activities and programs",
                        "hierarchy_level": 60,
                    },
                    {
                        "role_type": UserRole.RoleType.TRANSPORT_MANAGER,
                        "name": "Transport Manager",
                        "description": "Management of school transportation",
                        "hierarchy_level": 55,
                    },
                    {
                        "role_type": UserRole.RoleType.SUPPORT,
                        "name": "Support Staff",
                        "description": "General support staff",
                        "hierarchy_level": 55,
                    },
                    {
                        "role_type": UserRole.RoleType.HOSTEL_WARDEN,
                        "name": "Hostel Warden",
                        "description": "Management of student hostel facilities",
                        "hierarchy_level": 55,
                    },
                    {
                        "role_type": UserRole.RoleType.DRIVER,
                        "name": "Driver",
                        "description": "School transport driver",
                        "hierarchy_level": 50,
                    },
                ]

                created_count = 0
                updated_count = 0

                for role_data in staff_roles_data:
                    role, created = Role.objects.get_or_create(
                        role_type=role_data["role_type"],
                        institution=default_institution,
                        defaults={
                            "name": role_data["name"],
                            "description": role_data["description"],
                            "hierarchy_level": role_data["hierarchy_level"],
                            "is_system_role": True,
                            "status": "active",
                        },
                    )

                    if created:
                        created_count += 1
                        self.log_success(f"Created role: {role.name}")
                    else:
                        # Update existing role if needed
                        updated = False
                        if role.name != role_data["name"]:
                            role.name = role_data["name"]
                            updated = True
                        if role.description != role_data["description"]:
                            role.description = role_data["description"]
                            updated = True
                        if role.hierarchy_level != role_data["hierarchy_level"]:
                            role.hierarchy_level = role_data["hierarchy_level"]
                            updated = True
                        if role.status != "active":
                            role.status = "active"
                            updated = True

                        if updated:
                            role.save()
                            updated_count += 1
                            self.log_warning(f"Updated role: {role.name}")

                self.log_success(
                    f"Created {created_count} roles, updated {updated_count} roles"
                )
                self.fixed_seed_staff_roles = True
                return True

        except Exception as e:
            self.log_error(f"Error fixing seed_staff_roles: {e}")
            import traceback

            traceback.print_exc()
            return False

    def update_legal_documents(self):
        """Update legal documents with enhanced content."""
        self.log_info("Updating legal documents with enhanced content...")

        try:
            from apps.support.models import LegalDocument

            # Enhanced privacy policy content
            enhanced_privacy_content = """<h2>Executive Summary</h2>
<p>At Nexus School Management System ("we," "our," or "us"), we are committed to protecting your privacy and ensuring the security of your personal information. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our school management platform.</p>
<p>This policy applies to all users of our services, including administrators, teachers, students, parents, and other authorized personnel who access our platform.</p>

<h2>1. Information We Collect</h2>

<h3>1.1 Personal Information You Provide</h3>
<p>We collect information you provide directly to us, including:</p>
<ul>
<li><strong>Account Information:</strong> Name, email address, phone number, and role-specific details when you create an account</li>
<li><strong>Student Information:</strong> Academic records, attendance data, grades, and performance metrics</li>
<li><strong>Communication Data:</strong> Messages, announcements, and feedback submitted through our platform</li>
<li><strong>Support Requests:</strong> Information provided when contacting our support team</li>
</ul>

<h3>1.2 Information We Collect Automatically</h3>
<ul>
<li><strong>Usage Data:</strong> How you interact with our platform, including pages visited, features used, and time spent</li>
<li><strong>Device Information:</strong> IP address, browser type, operating system, and device identifiers</li>
<li><strong>Log Data:</strong> Server logs, error reports, and performance metrics</li>
<li><strong>Cookies and Tracking:</strong> Information collected through cookies and similar technologies</li>
</ul>

<h3>1.3 Information from Third Parties</h3>
<p>We may receive information from third-party services you connect to our platform, such as:</p>
<ul>
<li>Single sign-on providers (Google, Microsoft, etc.)</li>
<li>Educational institutions for data integration</li>
<li>Payment processors for billing information</li>
</ul>

<h2>2. How We Use Your Information</h2>
<p>We use the information we collect for the following purposes:</p>

<h3>2.1 Service Provision</h3>
<ul>
<li>To provide, maintain, and improve our school management services</li>
<li>To process transactions and manage subscriptions</li>
<li>To deliver personalized educational content and features</li>
<li>To ensure platform security and prevent unauthorized access</li>
</ul>

<h3>2.2 Communication</h3>
<ul>
<li>To send important updates, security alerts, and service notifications</li>
<li>To respond to your inquiries and provide customer support</li>
<li>To send educational announcements and academic communications</li>
<li>To provide technical assistance and troubleshooting</li>
</ul>

<h3>2.3 Analytics and Improvement</h3>
<ul>
<li>To analyze usage patterns and improve user experience</li>
<li>To develop new features and enhance existing functionality</li>
<li>To monitor system performance and identify issues</li>
<li>To conduct research and generate insights for educational improvement</li>
</ul>

<h3>2.4 Legal and Compliance</h3>
<ul>
<li>To comply with legal obligations and regulatory requirements</li>
<li>To protect against fraud, abuse, and security threats</li>
<li>To enforce our terms of service and acceptable use policies</li>
<li>To respond to legal requests and protect our rights</li>
</ul>

<h2>3. Information Sharing and Disclosure</h2>

<h3>3.1 With Your Consent</h3>
<p>We share your information when you explicitly consent to such sharing, including:</p>
<ul>
<li>When you authorize third-party integrations</li>
<li>When you share information through social features</li>
<li>When you participate in collaborative educational activities</li>
</ul>

<h3>3.2 Service Providers</h3>
<p>We share information with trusted third-party service providers who assist us in:</p>
<ul>
<li>Hosting and maintaining our platform infrastructure</li>
<li>Processing payments and managing subscriptions</li>
<li>Providing customer support and communication services</li>
<li>Analyzing platform usage and performance</li>
</ul>

<h3>3.3 Legal Requirements</h3>
<p>We may disclose your information if required by law or to protect rights and safety:</p>
<ul>
<li>In response to legal requests, court orders, or government inquiries</li>
<li>To protect against imminent harm to individuals or property</li>
<li>To investigate potential violations of our terms or policies</li>
<li>To enforce our agreements and protect our legal rights</li>
</ul>

<h3>3.4 Business Transfers</h3>
<p>In the event of a merger, acquisition, or sale of assets, your information may be transferred to the new entity, subject to continued protection under this privacy policy.</p>

<h2>4. Data Security</h2>
<p>We implement comprehensive security measures to protect your personal information:</p>

<h3>4.1 Technical Safeguards</h3>
<ul>
<li><strong>Encryption:</strong> Data encrypted in transit and at rest using industry-standard protocols</li>
<li><strong>Access Controls:</strong> Role-based access controls and multi-factor authentication</li>
<li><strong>Network Security:</strong> Firewalls, intrusion detection, and regular security audits</li>
<li><strong>Data Backup:</strong> Regular encrypted backups with secure storage</li>
</ul>

<h3>4.2 Administrative Controls</h3>
<ul>
<li><strong>Staff Training:</strong> Regular security awareness training for all personnel</li>
<li><strong>Access Management:</strong> Least-privilege access and regular access reviews</li>
<li><strong>Incident Response:</strong> Established procedures for security incidents</li>
<li><strong>Vendor Assessment:</strong> Security evaluations of third-party providers</li>
</ul>

<h3>4.3 Monitoring and Updates</h3>
<ul>
<li><strong>Security Monitoring:</strong> Continuous monitoring for suspicious activities</li>
<li><strong>Regular Audits:</strong> Periodic security assessments and penetration testing</li>
<li><strong>Software Updates:</strong> Timely application of security patches and updates</li>
</ul>

<h2>5. Your Rights and Controls</h2>

<h3>5.1 Access and Portability</h3>
<p>You have the right to:</p>
<ul>
<li><strong>Access:</strong> Request a copy of your personal information we hold</li>
<li><strong>Portability:</strong> Receive your data in a structured, machine-readable format</li>
<li><strong>Correction:</strong> Request correction of inaccurate or incomplete information</li>
</ul>

<h3>5.2 Deletion and Restriction</h3>
<ul>
<li><strong>Deletion:</strong> Request deletion of your personal information (subject to legal requirements)</li>
<li><strong>Restriction:</strong> Request limitation of processing in certain circumstances</li>
<li><strong>Objection:</strong> Object to processing based on legitimate interests</li>
</ul>

<h3>5.3 Communication Preferences</h3>
<ul>
<li><strong>Marketing Opt-out:</strong> Unsubscribe from marketing communications</li>
<li><strong>Notification Settings:</strong> Control notification preferences in your account</li>
<li><strong>Cookie Controls:</strong> Manage cookie preferences through your browser</li>
</ul>

<h2>6. Data Retention</h2>
<p>We retain your information only as long as necessary for the purposes outlined in this policy:</p>
<ul>
<li><strong>Account Data:</strong> Retained while your account is active and for a reasonable period after deactivation</li>
<li><strong>Educational Records:</strong> Retained according to educational record retention requirements</li>
<li><strong>Communication Logs:</strong> Retained for customer service and legal compliance purposes</li>
<li><strong>Analytics Data:</strong> Aggregated and anonymized data may be retained indefinitely</li>
</ul>

<h2>7. International Data Transfers</h2>
<p>Our services may involve transfers of data to countries outside your own. We ensure appropriate safeguards:</p>
<ul>
<li><strong>Adequacy Decisions:</strong> Transfers to countries with adequate data protection</li>
<li><strong>Standard Contracts:</strong> Use of approved contractual clauses</li>
<li><strong>Certification Schemes:</strong> Compliance with recognized certification frameworks</li>
<li><strong>Your Consent:</strong> Where required, obtaining explicit consent for transfers</li>
</ul>

<h2>8. Children's Privacy</h2>
<p>We are committed to protecting children's privacy in accordance with applicable laws:</p>
<ul>
<li><strong>Age Restrictions:</strong> Services may be restricted to users 13 years and older</li>
<li><strong>Parental Consent:</strong> Where required, we obtain parental consent for data collection</li>
<li><strong>Educational Data:</strong> Student information is handled in compliance with FERPA and similar regulations</li>
<li><strong>Privacy Notices:</strong> Clear communication about data collection to parents and guardians</li>
</ul>

<h2>9. Third-party Services</h2>

<h3>9.1 External Links</h3>
<p>Our platform may contain links to third-party websites. We are not responsible for the privacy practices of these external sites.</p>

<h3>9.2 Analytics Services</h3>
<p>We use analytics services to understand platform usage and improve our services. These services may collect anonymous usage data.</p>

<h3>9.3 Payment Processing</h3>
<p>Payment information is processed by secure third-party payment processors. We do not store payment card details on our servers.</p>

<h2>10. Cookies and Tracking Technologies</h2>
<p>We use cookies and similar technologies to enhance your experience:</p>

<h3>10.1 Essential Cookies</h3>
<p>Required for platform functionality, authentication, and security.</p>

<h3>10.2 Analytics Cookies</h3>
<p>Help us understand how users interact with our platform to improve services.</p>

<h3>10.3 Preference Cookies</h3>
<p>Remember your settings and preferences for a personalized experience.</p>

<h3>10.4 Marketing Cookies</h3>
<p>Used to deliver relevant advertisements and measure campaign effectiveness.</p>

<h2>11. Changes to This Privacy Policy</h2>

<h3>11.1 Updates</h3>
<p>We may update this privacy policy periodically to reflect changes in our practices or legal requirements.</p>

<h3>11.2 Notification</h3>
<ul>
<li><strong>Email Notification:</strong> We will notify you via email of material changes</li>
<li><strong>Platform Notice:</strong> Updates will be posted on our platform with effective dates</li>
<li><strong>Review History:</strong> Previous versions available upon request</li>
</ul>

<h3>11.3 Your Responsibility</h3>
<p>Please review this policy periodically. Continued use of our services after changes constitutes acceptance of the updated policy.</p>

<h2>12. Contact Information</h2>

<h3>12.1 Data Protection Officer</h3>
<div class="contact-info">
<p>For privacy-related inquiries, please contact our Data Protection Officer:</p>
<ul>
<li><strong>Email:</strong> privacy@nordalms.pythonanywhere.com</li>
<li><strong>Response Time:</strong> Within 30 days for data requests</li>
</ul>
</div>

<h3>12.2 General Support</h3>
<ul>
<li><strong>Email:</strong> support@nordalms.pythonanywhere.com</li>
<li><strong>Phone:</strong> +1 (555) 123-4567</li>
<li><strong>Hours:</strong> Monday - Friday, 9 AM - 6 PM EST</li>
</ul>

<h3>12.3 Postal Address</h3>
<address>
Nexus School Management System<br>
Attn: Data Protection Officer<br>
[Your Business Address]<br>
[City, State, ZIP Code]<br>
[Country]
</address>

<h2>13. Additional Resources</h2>
<ul>
<li><a href="/support/terms-of-service/">Terms of Service</a></li>
<li><a href="/support/cookie-policy/">Cookie Policy</a></li>
<li><a href="/support/data-protection/">Data Protection Policy</a></li>
<li><a href="/support/accessibility/">Accessibility Statement</a></li>
</ul>

<p><em>This privacy policy was last updated on December 17, 2025. Version 2.0</em></p>"""

            # Try to get existing privacy policy
            privacy_policy = LegalDocument.objects.get(document_type="privacy_policy")

            # Update the content
            privacy_policy.content = enhanced_privacy_content
            privacy_policy.version = "2.0"
            privacy_policy.title = "Privacy Policy"
            privacy_policy.save()

            self.log_success(
                f"Updated privacy policy (ID: {privacy_policy.id}) - {len(enhanced_privacy_content)} characters"
            )

        except LegalDocument.DoesNotExist:
            # Create new privacy policy if it doesn't exist
            privacy_policy = LegalDocument.objects.create(
                title="Privacy Policy",
                slug="privacy-policy",
                content=enhanced_privacy_content,
                document_type="privacy_policy",
                version="2.0",
                is_active=True,
            )

            self.log_success(
                f"Created new privacy policy (ID: {privacy_policy.id}) - {len(enhanced_privacy_content)} characters"
            )

        except Exception as e:
            self.log_error(f"Error updating privacy policy: {e}")
            return False

        # Enhanced Terms of Service content
        enhanced_terms_content = """<h2>Executive Summary</h2>
<p>Welcome to the Nexus School Management System ("the System"). These Terms of Service ("Terms") govern your access to and use of our comprehensive educational platform. By accessing or using our services, you agree to be bound by these Terms and our Privacy Policy.</p>
<p>Our platform provides a complete solution for educational institutions, including student management, academic tracking, communication tools, and administrative functions. These Terms ensure fair and responsible use of our services.</p>

<h2>1. Acceptance of Terms</h2>

<h3>1.1 Agreement to Terms</h3>
<p>By accessing and using the Nexus School Management System, you accept and agree to be bound by the terms and provision of this agreement. This agreement constitutes a legally binding contract between you and Nexus School Management System.</p>

<h3>1.2 Eligibility Requirements</h3>
<p>To use our services, you must:</p>
<ul>
<li>Be at least 13 years old or have parental consent</li>
<li>Have authority to enter into this agreement</li>
<li>Provide accurate and complete information</li>
<li>Maintain the security of your account credentials</li>
</ul>

<h3>1.3 Institutional Use</h3>
<p>Educational institutions may use our services subject to:</p>
<ul>
<li>Proper licensing and subscription agreements</li>
<li>Compliance with applicable educational regulations</li>
<li>Acceptance of these Terms by authorized representatives</li>
<li>Implementation of appropriate data protection measures</li>
</ul>

<h2>2. Description of Services</h2>

<h3>2.1 Platform Features</h3>
<p>The Nexus School Management System provides comprehensive educational management tools:</p>

<h4>Academic Management</h4>
<ul>
<li><strong>Student Records:</strong> Complete academic profiles and performance tracking</li>
<li><strong>Grade Management:</strong> Automated grading and progress reporting</li>
<li><strong>Curriculum Planning:</strong> Course scheduling and academic planning tools</li>
<li><strong>Assessment Tools:</strong> Quiz creation and evaluation systems</li>
</ul>

<h4>Administrative Functions</h4>
<ul>
<li><strong>User Management:</strong> Role-based access control and user administration</li>
<li><strong>Communication:</strong> Announcements, messaging, and notification systems</li>
<li><strong>Reporting:</strong> Comprehensive analytics and reporting dashboards</li>
<li><strong>Resource Management:</strong> Library, transportation, and facility management</li>
</ul>

<h4>Support Services</h4>
<ul>
<li><strong>Help Center:</strong> Knowledge base and self-service support</li>
<li><strong>Technical Support:</strong> Assistance with platform usage and troubleshooting</li>
<li><strong>Training Resources:</strong> Documentation and training materials</li>
<li><strong>Community Forums:</strong> User-to-user support and knowledge sharing</li>
</ul>

<h3>2.2 Service Availability</h3>
<ul>
<li><strong>Uptime Commitment:</strong> 99.5% uptime excluding scheduled maintenance</li>
<li><strong>Maintenance Windows:</strong> Scheduled maintenance during off-peak hours</li>
<li><strong>Emergency Maintenance:</strong> Unscheduled maintenance with advance notice when possible</li>
<li><strong>Service Updates:</strong> Regular feature updates and security patches</li>
</ul>

<h2>3. User Accounts and Responsibilities</h2>

<h3>3.1 Account Creation and Management</h3>
<p>Users are responsible for:</p>
<ul>
<li>Providing accurate registration information</li>
<li>Maintaining current contact and profile information</li>
<li>Protecting account credentials and access</li>
<li>Notifying us of unauthorized account access</li>
<li>Ensuring proper use by authorized personnel only</li>
</ul>

<h3>3.2 User Conduct and Acceptable Use</h3>

<h4>Permitted Use</h4>
<ul>
<li>Educational and administrative purposes only</li>
<li>Authorized access by licensed users</li>
<li>Compliance with institutional policies</li>
<li>Respect for intellectual property rights</li>
</ul>

<h4>Prohibited Activities</h4>
<ul>
<li>Unauthorized access or use of other accounts</li>
<li>Sharing login credentials with unauthorized users</li>
<li>Attempting to circumvent security measures</li>
<li>Uploading malicious content or code</li>
<li>Violating applicable laws or regulations</li>
<li>Harassing or abusing other users</li>
<li>Impersonating other individuals or institutions</li>
</ul>

<h3>3.3 Data Protection and Privacy</h3>
<p>Users must:</p>
<ul>
<li>Comply with data protection laws (FERPA, GDPR, etc.)</li>
<li>Obtain necessary consents for data collection</li>
<li>Implement appropriate security measures</li>
<li>Report data breaches promptly</li>
<li>Respect student and user privacy rights</li>
</ul>

<h2>4. Intellectual Property Rights</h2>

<h3>4.1 Our Intellectual Property</h3>
<p>The Nexus School Management System and its content are protected by intellectual property laws:</p>
<ul>
<li><strong>Software and Code:</strong> Proprietary software protected by copyright</li>
<li><strong>Trademarks:</strong> Nexus and related marks are our trademarks</li>
<li><strong>Documentation:</strong> User guides and help content are copyrighted</li>
<li><strong>Database Rights:</strong> Data structures and organization are protected</li>
</ul>

<h3>4.2 User Content</h3>
<ul>
<li><strong>Ownership:</strong> Users retain ownership of their content</li>
<li><strong>License Grant:</strong> Users grant us license to use content for service provision</li>
<li><strong>Content Standards:</strong> Content must not violate laws or our policies</li>
<li><strong>Removal Rights:</strong> We may remove inappropriate content</li>
</ul>

<h3>4.3 Educational Content</h3>
<ul>
<li><strong>Fair Use:</strong> Educational use of copyrighted materials under fair use doctrine</li>
<li><strong>Licensing:</strong> Open educational resources and licensed content</li>
<li><strong>Attribution:</strong> Proper attribution of source materials</li>
<li><strong>Copyright Compliance:</strong> Respect for intellectual property in educational materials</li>
</ul>

<h2>5. Fees and Payment Terms</h2>

<h3>5.1 Subscription Fees</h3>
<p>Service fees are based on:</p>
<ul>
<li>Number of users and institutions</li>
<li>Selected feature modules</li>
<li>Service level agreements</li>
<li>Contract duration and terms</li>
</ul>

<h3>5.2 Payment Methods</h3>
<ul>
<li><strong>Accepted Methods:</strong> Credit cards, bank transfers, and approved payment processors</li>
<li><strong>Billing Cycle:</strong> Monthly or annual billing based on subscription plan</li>
<li><strong>Auto-Renewal:</strong> Subscriptions renew automatically unless cancelled</li>
<li><strong>Late Payments:</strong> Service suspension for overdue accounts</li>
</ul>

<h3>5.3 Refunds and Credits</h3>
<ul>
<li><strong>Refund Policy:</strong> Refunds for unused prepaid services within 30 days</li>
<li><strong>Service Credits:</strong> Credits for service outages exceeding agreed levels</li>
<li><strong>Disputes:</strong> Payment disputes handled through our support channels</li>
<li><strong>Tax Compliance:</strong> All fees subject to applicable taxes</li>
</ul>

<h2>6. Service Level Agreements</h2>

<h3>6.1 Performance Standards</h3>
<p>We commit to:</p>
<ul>
<li><strong>System Availability:</strong> 99.5% uptime during business hours</li>
<li><strong>Response Times:</strong> Support response within 24 hours</li>
<li><strong>Data Backup:</strong> Daily backups with disaster recovery</li>
<li><strong>Security:</strong> Industry-standard security measures</li>
</ul>

<h3>6.2 Support Services</h3>
<ul>
<li><strong>Technical Support:</strong> 24/7 monitoring and support</li>
<li><strong>Help Desk:</strong> Multiple support channels and resources</li>
<li><strong>Training:</strong> User training and onboarding support</li>
<li><strong>Updates:</strong> Regular software updates and improvements</li>
</ul>

<h3>6.3 Maintenance and Updates</h3>
<ul>
<li><strong>Scheduled Maintenance:</strong> Announced maintenance windows</li>
<li><strong>Emergency Updates:</strong> Critical security and bug fixes</li>
<li><strong>Feature Releases:</strong> Regular feature updates and enhancements</li>
<li><strong>Compatibility:</strong> Support for current browser and device versions</li>
</ul>

<h2>7. Data Security and Privacy</h2>

<h3>7.1 Security Measures</h3>
<p>We implement comprehensive security:</p>
<ul>
<li><strong>Encryption:</strong> Data encrypted in transit and at rest</li>
<li><strong>Access Controls:</strong> Role-based permissions and authentication</li>
<li><strong>Monitoring:</strong> Continuous security monitoring and alerts</li>
<li><strong>Incident Response:</strong> Established procedures for security incidents</li>
</ul>

<h3>7.2 Data Protection</h3>
<ul>
<li><strong>Compliance:</strong> Adherence to FERPA, GDPR, and other regulations</li>
<li><strong>Data Minimization:</strong> Collection of only necessary data</li>
<li><strong>Retention Policies:</strong> Defined data retention and deletion procedures</li>
<li><strong>Privacy Rights:</strong> Support for user data rights and requests</li>
</ul>

<h3>7.3 Breach Notification</h3>
<ul>
<li><strong>Notification Timeline:</strong> Notification within 72 hours of discovery</li>
<li><strong>Regulatory Compliance:</strong> Compliance with breach notification laws</li>
<li><strong>User Communication:</strong> Clear communication about breach impacts</li>
<li><strong>Remediation:</strong> Steps to mitigate breach effects</li>
</ul>

<h2>8. Termination and Suspension</h2>

<h3>8.1 Termination by User</h3>
<p>Users may terminate their accounts:</p>
<ul>
<li>Through account settings or contacting support</li>
<li>With appropriate notice periods</li>
<li>Following data export procedures</li>
<li>Subject to outstanding payment obligations</li>
</ul>

<h3>8.2 Termination by Us</h3>
<p>We may terminate or suspend services for:</p>
<ul>
<li>Violation of these Terms</li>
<li>Non-payment of fees</li>
<li>Illegal or harmful activities</li>
<li>At the end of subscription periods</li>
</ul>

<h3>8.3 Effect of Termination</h3>
<ul>
<li><strong>Data Export:</strong> Opportunity to export data before termination</li>
<li><strong>Access Removal:</strong> Immediate cessation of service access</li>
<li><strong>Data Retention:</strong> Retention according to legal requirements</li>
<li><strong>Continued Obligations:</strong> Survival of certain provisions</li>
</ul>

<h2>9. Disclaimers and Limitations</h2>

<h3>9.1 Service Disclaimers</h3>
<p>The services are provided "as is" and "as available":</p>
<ul>
<li>No warranties of merchantability or fitness for purpose</li>
<li>No guarantee of uninterrupted or error-free service</li>
<li>No liability for data loss or service interruptions</li>
<li>No warranty of compatibility with all systems</li>
</ul>

<h3>9.2 Limitation of Liability</h3>
<ul>
<li><strong>Direct Damages:</strong> Limited to fees paid in the preceding 12 months</li>
<li><strong>Indirect Damages:</strong> No liability for indirect or consequential damages</li>
<li><strong>Data Loss:</strong> No liability for data loss or corruption</li>
<li><strong>Third-Party Claims:</strong> No liability for third-party actions or claims</li>
</ul>

<h3>9.3 Force Majeure</h3>
<p>We are not liable for failures due to:</p>
<ul>
<li>Natural disasters or acts of God</li>
<li>War, terrorism, or civil unrest</li>
<li>Government actions or regulations</li>
<li>Internet or telecommunications failures</li>
</ul>

<h2>10. Indemnification</h2>

<h3>10.1 User Indemnification</h3>
<p>You agree to indemnify and hold us harmless from:</p>
<ul>
<li>Claims arising from your use of the services</li>
<li>Violation of these Terms or applicable laws</li>
<li>Infringement of third-party intellectual property</li>
<li>Unauthorized access or misuse of your account</li>
</ul>

<h3>10.2 Our Indemnification</h3>
<p>We agree to indemnify you for:</p>
<ul>
<li>Claims of intellectual property infringement by our services</li>
<li>Third-party claims related to our negligence</li>
<li>Breach of data security warranties</li>
</ul>

<h2>11. Dispute Resolution</h2>

<h3>11.1 Informal Resolution</h3>
<p>Disputes should first be resolved through:</p>
<ul>
<li>Contacting our support team</li>
<li>Escalating to account management</li>
<li>Mediation or alternative dispute resolution</li>
</ul>

<h3>11.2 Governing Law</h3>
<ul>
<li><strong>Jurisdiction:</strong> Disputes governed by laws of [Jurisdiction]</li>
<li><strong>Venue:</strong> Exclusive venue in competent courts of [Jurisdiction]</li>
<li><strong>Class Actions:</strong> No class action lawsuits permitted</li>
<li><strong>Arbitration:</strong> Binding arbitration for certain disputes</li>
</ul>

<h3>11.3 Legal Compliance</h3>
<ul>
<li><strong>Export Controls:</strong> Compliance with applicable export laws</li>
<li><strong>Sanctions:</strong> No services to sanctioned individuals or entities</li>
<li><strong>Local Laws:</strong> Compliance with local laws and regulations</li>
</ul>

<h2>12. Changes to Terms</h2>

<h3>12.1 Modifications</h3>
<p>We may modify these Terms:</p>
<ul>
<li>With reasonable notice to users</li>
<li>For legal, regulatory, or operational reasons</li>
<li>To reflect new features or services</li>
<li>To improve clarity or user experience</li>
</ul>

<h3>12.2 User Notification</h3>
<ul>
<li><strong>Email Notification:</strong> Direct email notification of changes</li>
<li><strong>Platform Notice:</strong> Prominent notice on the platform</li>
<li><strong>Review Period:</strong> Reasonable time to review changes</li>
<li><strong>Objection Rights:</strong> Right to terminate if changes unacceptable</li>
</ul>

<h3>12.3 Acceptance of Changes</h3>
<ul>
<li><strong>Continued Use:</strong> Continued use constitutes acceptance</li>
<li><strong>Express Acceptance:</strong> Explicit acceptance through account actions</li>
<li><strong>Version History:</strong> Access to previous versions of Terms</li>
</ul>

<h2>13. Miscellaneous Provisions</h2>

<h3>13.1 Severability</h3>
<p>If any provision is found invalid, the remaining provisions remain in effect.</p>

<h3>13.2 Entire Agreement</h3>
<p>These Terms constitute the entire agreement between parties.</p>

<h3>13.3 Waiver</h3>
<p>Failure to enforce provisions does not constitute waiver of rights.</p>

<h3>13.4 Assignment</h3>
<p>Rights may not be assigned without written consent.</p>

<h3>13.5 Third-Party Beneficiaries</h3>
<p>These Terms do not create rights for third parties.</p>

<h2>14. Contact Information</h2>

<h3>14.1 General Support</h3>
<div class="contact-info">
<p>For questions about these Terms, please contact:</p>
<ul>
<li><strong>Email:</strong> legal@nordalms.pythonanywhere.com</li>
<li><strong>Support:</strong> support@nordalms.pythonanywhere.com</li>
<li><strong>Phone:</strong> +1 (555) 123-4567</li>
<li><strong>Hours:</strong> Monday - Friday, 9 AM - 6 PM EST</li>
</ul>
</div>

<h3>14.2 Legal Department</h3>
<address>
Nexus School Management System<br>
Legal Department<br>
Attn: Terms of Service<br>
[Your Business Address]<br>
[City, State, ZIP Code]<br>
[Country]
</address>

<h2>15. Additional Resources</h2>
<ul>
<li><a href="/support/privacy-policy/">Privacy Policy</a></li>
<li><a href="/support/cookie-policy/">Cookie Policy</a></li>
<li><a href="/support/data-protection/">Data Protection Policy</a></li>
<li><a href="/support/acceptable-use/">Acceptable Use Policy</a></li>
</ul>

<p><em>These Terms of Service were last updated on December 17, 2025. Version 2.0</em></p>"""

        try:
            # Try to get existing Terms of Service
            terms_of_service = LegalDocument.objects.get(
                document_type="terms_of_service"
            )

            # Update the content
            terms_of_service.content = enhanced_terms_content
            terms_of_service.version = "2.0"
            terms_of_service.title = "Terms of Service"
            terms_of_service.save()

            self.log_success(
                f"Updated Terms of Service (ID: {terms_of_service.id}) - {len(enhanced_terms_content)} characters"
            )

        except LegalDocument.DoesNotExist:
            # Create new Terms of Service if it doesn't exist
            terms_of_service = LegalDocument.objects.create(
                title="Terms of Service",
                slug="terms-of-service",
                content=enhanced_terms_content,
                document_type="terms_of_service",
                version="2.0",
                is_active=True,
                requires_acknowledgment=True,
            )

            self.log_success(
                f"Created new Terms of Service (ID: {terms_of_service.id}) - {len(enhanced_terms_content)} characters"
            )

        except Exception as e:
            self.log_error(f"Error updating Terms of Service: {e}")
            return False

        return True

    def run_all_setup_commands(self):
        """Run all setup commands in proper order."""
        # Skip seed_staff_roles and default institution creation
        # Roles will be created per institution when institutions are manually created
        self.log_info(
            "Skipping automatic role seeding - roles will be created per institution"
        )

        # Skip updating legal documents during setup (requires institution)
        self.log_info(
            "Skipping legal document updates - will be handled per institution"
        )

        # Define the order of commands to run
        setup_commands = [
            # Core setup commands
            ("setup_multitenancy", "Setting up multi-tenancy..."),
            # System-wide data (now works with GlobalBaseModel)
            ("create_system_kpis", "Creating system KPIs..."),
            ("create_system_reports", "Creating system reports..."),
            # Populate data commands (some may still fail due to institution requirements)
            ("populate_exam_types", "Populating exam types..."),
            ("populate_faqs", "Populating FAQs..."),
            ("populate_legal_documents", "Populating legal documents..."),
            ("populate_grade_levels", "Populating grade levels..."),
            # Skip permission assignment until institutions are created
            # ("assign_role_permissions", "Assigning role permissions..."),
            # ("sync_permissions", "Synchronizing user permissions..."),
            ("map_unmapped_users", "Mapping unmapped users..."),
            # Data collection
            ("collect_system_metrics", "Collecting system metrics..."),
        ]

        # Execute commands
        for command_name, description in setup_commands:
            self.log_info(description)
            self.run_command(command_name)

        # No default institution created - will be created manually via admin interface
        self.log_info(
            "No default institution created - create institutions manually via Django admin"
        )

        # Run any additional populate_* commands found
        self.run_additional_populate_commands()

    def run_additional_populate_commands(self):
        """Run any additional populate_* commands that weren't explicitly listed."""
        from django.core.management import get_commands

        all_commands = get_commands()
        populate_commands = [
            cmd for cmd in all_commands.keys() if cmd.startswith("populate_")
        ]

        # Exclude already run commands
        already_run = [
            "populate_exam_types",
            "populate_faqs",
            "populate_legal_documents",
            "populate_grade_levels",
        ]
        new_commands = [cmd for cmd in populate_commands if cmd not in already_run]

        if new_commands:
            self.log_info(f"Found {len(new_commands)} additional populate commands")
            for command_name in new_commands:
                self.run_command(command_name)

    def prompt_yes_no(self, question):
        """Prompt user for yes/no input."""
        while True:
            response = input(f"{question} ").strip().lower()
            if response in ["y", "yes"]:
                return True
            elif response in ["n", "no"]:
                return False
            else:
                print("Please answer 'y' or 'n'")

    def create_institution_interactive(self):
        """Interactively create a new institution."""
        self.log_info("\nCreating a new institution...")

        try:
            # Get institution details from user
            name = input("Institution name: ").strip()
            if not name:
                self.log_warning("Institution creation skipped - no name provided")
                return

            code = input("Institution code (for subdomain): ").strip()
            if not code:
                self.log_warning("Institution creation skipped - no code provided")
                return

            admin_email = input("Admin email address: ").strip()
            if not admin_email:
                self.log_warning(
                    "Institution creation skipped - no admin email provided"
                )
                return

            # Optional fields
            description = input("Description (optional): ").strip()
            phone = input("Phone number (optional): ").strip()
            address = input("Address (optional): ").strip()

            # Build command arguments
            args = [name, code, f"--admin_email={admin_email}"]

            if description:
                args.append(f"--description={description}")
            if phone:
                args.append(f"--phone={phone}")
            if address:
                args.append(f"--address={address}")

            # Ask if this should be default institution
            if self.prompt_yes_no("Set as default institution? (y/n): "):
                args.append("--set_default")

            # Run the create_institution command
            self.log_info(f"Creating institution: {name} ({code})")
            self.run_command("create_institution", *args)

        except KeyboardInterrupt:
            self.log_warning("Institution creation cancelled by user")
        except Exception as e:
            self.log_error(f"Error creating institution: {e}")

    def create_superuser_interactive(self):
        """Interactively create a superuser."""
        self.log_info("\nCreating superuser account...")

        try:
            # Check if superuser already exists
            if User.objects.filter(is_superuser=True).exists():
                self.log_warning("Superuser already exists.")
                if not self.prompt_yes_no(
                    "Do you want to create another superuser? (y/n): "
                ):
                    return None

            # Get credentials from user
            print("\nPlease enter superuser credentials:")

            email = input("Email address: ").strip()

            # Validate email
            if not email or "@" not in email:
                self.log_error("Invalid email address")
                if self.prompt_yes_no("Try again? (y/n): "):
                    return self.create_superuser_interactive()
                return None

            # Get password (twice for confirmation)
            while True:
                password = getpass.getpass("Password: ").strip()
                confirm_password = getpass.getpass("Confirm password: ").strip()

                if not password:
                    print("Password cannot be empty")
                    if not self.prompt_yes_no("Try again? (y/n): "):
                        return None
                    continue

                if password != confirm_password:
                    print("Passwords do not match")
                    if not self.prompt_yes_no("Try again? (y/n): "):
                        return None
                else:
                    break

            # Create superuser
            try:
                # User model uses email as username
                user = User.objects.create_superuser(email=email, password=password)

                self.log_success(f"Superuser created successfully: {email}")
                return user

            except Exception as e:
                self.log_error(f"Error creating superuser: {e}")
                if self.prompt_yes_no("Try again? (y/n): "):
                    return self.create_superuser_interactive()

        except KeyboardInterrupt:
            self.log_warning("Superuser creation cancelled by user")
            return None
        except Exception as e:
            self.log_error(f"Unexpected error: {e}")
            return None

    def create_school_admin_interactive(self):
        """Interactively create a school admin."""
        self.log_info("\nCreating school admin account...")

        try:
            from apps.core.models import Institution
            from apps.users.models import Role, UserRole

            # Get or create default institution
            default_institution = Institution.objects.filter(code="DEFAULT").first()
            if not default_institution:
                self.log_info("Creating default institution...")
                default_institution = Institution.objects.create(
                    name="Default School",
                    code="DEFAULT",
                    short_name="Default",
                    description="Default institution",
                    institution_type="high_school",
                    ownership_type="private",
                    is_active=True,
                    allows_online_enrollment=True,
                    requires_parent_approval=True,
                )
                self.log_success(
                    f"Created default institution: {default_institution.name}"
                )

            # Check if school admin already exists for this institution
            school_admin_role = Role.objects.filter(
                role_type=Role.RoleType.SCHOOL_ADMIN, institution=default_institution
            ).first()

            if not school_admin_role:
                # Create the SCHOOL_ADMIN role if it doesn't exist
                school_admin_role = Role.objects.create(
                    role_type=Role.RoleType.SCHOOL_ADMIN,
                    name="School Administrator",
                    description="School-level administrator with comprehensive management permissions",
                    hierarchy_level=95,
                    institution=default_institution,
                    is_system_role=True,
                    status="active",
                )
                self.log_success(f"Created SCHOOL_ADMIN role: {school_admin_role.name}")

            # Check if school admin user already exists
            existing_admins = UserRole.objects.filter(
                role=school_admin_role, institution=default_institution
            ).select_related("user")

            if existing_admins.exists():
                admin_emails = [ur.user.email for ur in existing_admins]
                self.log_warning(
                    f"School admin already exists: {', '.join(admin_emails)}"
                )
                if not self.prompt_yes_no(
                    "Do you want to create another school admin? (y/n): "
                ):
                    return None

            # Get credentials from user
            print("\nPlease enter school admin credentials:")

            email = input("Email address: ").strip()

            # Validate email
            if not email or "@" not in email:
                self.log_error("Invalid email address")
                if self.prompt_yes_no("Try again? (y/n): "):
                    return self.create_school_admin_interactive()
                return None

            # Check if user already exists
            existing_user = User.objects.filter(email=email).first()
            if existing_user:
                self.log_warning(f"User with email {email} already exists")
                if not self.prompt_yes_no(
                    "Do you want to assign the school admin role to this user? (y/n): "
                ):
                    if self.prompt_yes_no("Try again with a different email? (y/n): "):
                        return self.create_school_admin_interactive()
                    return None
                user = existing_user
                created = False
            else:
                # Get password (twice for confirmation)
                while True:
                    password = getpass.getpass("Password: ").strip()
                    confirm_password = getpass.getpass("Confirm password: ").strip()

                    if not password:
                        print("Password cannot be empty")
                        if not self.prompt_yes_no("Try again? (y/n): "):
                            return None
                        continue

                    if password != confirm_password:
                        print("Passwords do not match")
                        if not self.prompt_yes_no("Try again? (y/n): "):
                            return None
                    else:
                        break

                # Create user
                try:
                    user = User.objects.create_user(
                        email=email,
                        password=password,
                        is_staff=True,
                        is_active=True,
                        is_verified=True,
                    )
                    created = True
                    self.log_success(f"School admin user created successfully: {email}")
                except Exception as e:
                    self.log_error(f"Error creating school admin user: {e}")
                    if self.prompt_yes_no("Try again? (y/n): "):
                        return self.create_school_admin_interactive()
                    return None

            # Assign school admin role
            try:
                # Check if user already has this role
                existing_role_assignment = UserRole.objects.filter(
                    user=user, role=school_admin_role, institution=default_institution
                ).first()

                if existing_role_assignment:
                    self.log_warning(f"User {email} already has SCHOOL_ADMIN role")
                    return user

                # Create the role assignment
                user_role = UserRole.objects.create(
                    user=user,
                    role=school_admin_role,
                    institution=default_institution,
                    is_primary=True,
                )

                self.log_success(f"Assigned SCHOOL_ADMIN role to {email}")

                # Sync permissions
                from apps.users.models import sync_user_permissions

                sync_user_permissions(user)

                return user

            except Exception as e:
                self.log_error(f"Error assigning school admin role: {e}")
                if created and self.prompt_yes_no(
                    "Delete the created user and try again? (y/n): "
                ):
                    user.delete()
                    return self.create_school_admin_interactive()
                return None

        except KeyboardInterrupt:
            self.log_warning("School admin creation cancelled by user")
            return None
        except Exception as e:
            self.log_error(f"Unexpected error: {e}")
            return None

    def create_school_admin_auto(self):
        """Automatically create a default school admin if one doesn't exist."""
        self.log_info("Checking for existing school admin...")

        try:
            from apps.core.models import Institution
            from apps.users.models import Role, UserRole

            # Get or create default institution
            default_institution = Institution.objects.filter(code="DEFAULT").first()
            if not default_institution:
                self.log_info("Creating default institution...")
                default_institution = Institution.objects.create(
                    name="Default School",
                    code="DEFAULT",
                    short_name="Default",
                    description="Default institution",
                    institution_type="high_school",
                    ownership_type="private",
                    is_active=True,
                    allows_online_enrollment=True,
                    requires_parent_approval=True,
                )
                self.log_success(
                    f"Created default institution: {default_institution.name}"
                )

            # Check if school admin role exists
            school_admin_role = Role.objects.filter(
                role_type=Role.RoleType.SCHOOL_ADMIN, institution=default_institution
            ).first()

            if not school_admin_role:
                # Create the SCHOOL_ADMIN role if it doesn't exist
                school_admin_role = Role.objects.create(
                    role_type=Role.RoleType.SCHOOL_ADMIN,
                    name="School Administrator",
                    description="School-level administrator with comprehensive management permissions",
                    hierarchy_level=95,
                    institution=default_institution,
                    is_system_role=True,
                    status="active",
                )
                self.log_success(f"Created SCHOOL_ADMIN role: {school_admin_role.name}")

            # Check if school admin user already exists
            existing_admins = UserRole.objects.filter(
                role=school_admin_role, institution=default_institution
            ).select_related("user")

            if existing_admins.exists():
                admin_emails = [ur.user.email for ur in existing_admins]
                self.log_info(
                    f"School admin already exists: {', '.join(admin_emails)} - skipping creation"
                )
                return existing_admins.first().user

            # Create default school admin user
            default_email = "admin@school.com"
            default_password = "admin123"

            # Check if user with this email already exists
            existing_user = User.objects.filter(email=default_email).first()
            if existing_user:
                self.log_info(
                    f"User {default_email} already exists - assigning school admin role"
                )
                user = existing_user
                created = False
            else:
                # Create new user
                user = User.objects.create_user(
                    email=default_email,
                    password=default_password,
                    is_staff=True,
                    is_active=True,
                    is_verified=True,
                )
                created = True
                self.log_success(f"Created school admin user: {default_email}")

            # Assign school admin role
            try:
                # Check if user already has this role
                existing_role_assignment = UserRole.objects.filter(
                    user=user, role=school_admin_role, institution=default_institution
                ).first()

                if existing_role_assignment:
                    self.log_info(f"User {default_email} already has SCHOOL_ADMIN role")
                    return user

                # Create the role assignment
                user_role = UserRole.objects.create(
                    user=user,
                    role=school_admin_role,
                    institution=default_institution,
                    is_primary=True,
                )

                self.log_success(f"Assigned SCHOOL_ADMIN role to {default_email}")

                # Sync permissions
                from apps.users.models import sync_user_permissions

                sync_user_permissions(user)

                if created:
                    self.log_info("Default school admin credentials:")
                    self.log_info(f"  Email: {default_email}")
                    self.log_info(f"  Password: {default_password}")
                    self.log_warning(
                        "⚠ Please change the default password after first login!"
                    )

                return user

            except Exception as e:
                self.log_error(f"Error assigning school admin role: {e}")
                if created:
                    user.delete()
                    self.log_error(
                        "Deleted created user due to role assignment failure"
                    )
                return None

        except Exception as e:
            self.log_error(f"Unexpected error creating school admin: {e}")
            return None

    def run_all_setup(self):
        """Run all setup functions in proper order."""
        print("=" * 60)
        print(" SCHOOL MANAGEMENT SYSTEM - COMPLETE SETUP ")
        print("=" * 60)
        print()

        try:
            # Step 1: Run migrations
            self.log_info("Step 1: Running database migrations...")
            if not self.run_migrations():
                self.log_error("Setup aborted due to migration failures")
                return False

            print()
            print("-" * 60)

            # Step 2: Run all setup commands
            self.log_info("Step 2: Running system setup commands...")
            self.run_all_setup_commands()

            print()
            print("-" * 60)

            # Step 3: Create superuser
            self.log_info("Step 3: Creating superuser...")
            self.create_superuser_interactive()

            # Step 4: Display summary
            self.display_summary()

            return True

        except Exception as e:
            self.log_error(f"Setup failed with error: {e}")
            import traceback

            traceback.print_exc()
            return False

    def display_summary(self):
        """Display setup summary."""
        print()
        print("=" * 60)
        self.log_success("SYSTEM SETUP COMPLETE!")
        print("=" * 60)

        if self.success_commands:
            print(f"\nSuccessfully executed {len(self.success_commands)} commands:")
            for cmd in self.success_commands:
                print(f"  ✓ {cmd}")

        if self.failed_commands:
            print(f"\nFailed to execute {len(self.failed_commands)} commands:")
            for cmd, error in self.failed_commands:
                print(f"  ✗ {cmd}: {error[:50]}...")

        # Display helpful next steps
        print("\nNEXT STEPS:")
        print("1. Start the development server: python manage.py runserver")
        print("2. Access the admin panel at: http://localhost:8000/admin/")
        print("3. CREATE YOUR FIRST INSTITUTION:")
        print("   - Go to: http://localhost:8000/admin/core/institution/")
        print("   - Click 'Add institution' in the top right")
        print("   - Fill in the required fields (name, code)")
        print("   - This will automatically create roles for that institution")
        print("4. Review system settings")
        print("5. Add additional users and data as needed")
        print("6. Test the system functionality")

        print("\n⚠  IMPORTANT: No default institution was created during setup.")
        print("   You must create at least one institution via the admin interface")
        print("   before you can add users, roles, or other institution-specific data.")

        if self.failed_commands:
            print("\n⚠  Some commands failed. You may need to run them manually.")
            print("   Check the error messages above for details.")


def main():
    """Main execution function."""
    try:
        creator = SystemCreator()

        # Confirm user wants to proceed
        print("This script will:")
        print("1. Run database migrations (makemigrations and migrate)")
        print("2. Execute all system setup commands")
        print("3. Create a superuser account")
        print("4. Set up the complete school management system")
        print()
        print("NOTE: No default institution or roles are created automatically.")
        print(
            "      You must create institutions manually via the Django admin interface."
        )
        print()
        print("WARNING: This will modify your database.")
        print("Make sure you have backups if needed.")
        print()

        response = input("Do you want to proceed? (y/n): ").strip().lower()
        if response not in ["y", "yes"]:
            print("Setup cancelled.")
            return 0

        # Run setup
        start_time = time.time()
        success = creator.run_all_setup()
        end_time = time.time()

        if success:
            print(
                f"\n🎉 Setup completed successfully in {end_time - start_time:.2f} seconds!"
            )
            print("\nTo start the development server, run:")
            print("    python manage.py runserver")
            return 0
        else:
            print(f"\n❌ Setup failed or was incomplete.")
            return 1

    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n✗ Setup failed with unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

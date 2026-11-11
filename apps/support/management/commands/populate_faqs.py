from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.support.models import FAQ, Category


class Command(BaseCommand):
    help = 'Populate the database with initial FAQs for the support system'

    def handle(self, *args, **options):
        # Ensure categories exist first
        self.create_categories()

        # Define the FAQ data organized by category
        faqs_data = [
            # Account & Login (existing + new)
            {
                'question': 'How do I reset my password?',
                'answer': '''
To reset your password:

1. Go to the login page and click "Forgot Password?"
2. Enter your email address
3. Check your email for a password reset link
4. Follow the link to create a new password

If you don't receive the email, please contact support or check your spam folder.
                ''',
                'category_slug': 'account-login',
                'order': 1
            },
            {
                'question': 'How do I change my profile information?',
                'answer': '''
To update your profile:

1. Log in to your account
2. Go to your profile/dashboard
3. Click on "Edit Profile" or "Account Settings"
4. Update your information as needed
5. Save your changes

For students, some information may be managed by school administrators.
                ''',
                'category_slug': 'account-login',
                'order': 2
            },
            {
                'question': 'Why can\'t I log in to my account?',
                'answer': '''
Common login issues and solutions:

**Wrong credentials**: Double-check your username/email and password (note: passwords are case-sensitive)

**Account locked**: After several failed attempts, accounts may be temporarily locked. Wait 15 minutes or contact support.

**Browser issues**: Clear your browser cache/cookies or try a different browser.

**System maintenance**: The system may be down for maintenance. Check the school website for announcements.

If none of these work, please contact support with your username/email address.
                ''',
                'category_slug': 'account-login',
                'order': 3
            },
            {
                'question': 'How do I enable two-factor authentication?',
                'answer': '''
To enhance your account security:

1. Log in to your account
2. Go to "Account Settings" > "Security"
3. Click "Enable Two-Factor Authentication"
4. Follow the setup process using your authenticator app
5. Save your backup codes in a safe place

2FA is recommended for all users to protect your account.
                ''',
                'category_slug': 'account-login',
                'order': 4
            },
            {
                'question': 'How do I switch between different user roles?',
                'answer': '''
If you have multiple roles (e.g., student and parent):

1. Log in with your primary account
2. Click on your profile picture/initials
3. Select "Switch Role" from the dropdown
4. Choose the role you want to use
5. The interface will update for that role

Some features may only be available in certain roles.
                ''',
                'category_slug': 'account-login',
                'order': 5
            },

            # Academic Information (existing + new)
            {
                'question': 'How can I view my grades and academic records?',
                'answer': '''
To view your academic information:

1. Log in to your student portal
2. Navigate to "Academics" or "Grades" section
3. Select the academic year/term you want to view
4. Click on individual subjects for detailed grade breakdowns

Parents can view their children's academic records through the parent portal by selecting their student first.
                ''',
                'category_slug': 'academic-records',
                'order': 1
            },
            {
                'question': 'How do I register for classes?',
                'answer': '''
Course registration process:

1. Log in during the registration period announced by your school
2. Go to "Academics" > "Course Registration"
3. Browse available courses by subject/department
4. Select your preferred courses (respecting prerequisites and schedule conflicts)
5. Submit your registration for approval

Check with your academic advisor for course recommendations.
                ''',
                'category_slug': 'academic-records',
                'order': 2
            },
            {
                'question': 'What is my class schedule and how can I view it?',
                'answer': '''
To view your class schedule:

1. Log in to your student portal
2. Go to "Schedule" or "Timetable"
3. Select the current term/academic year
4. Your schedule will show class times, locations, and instructors

You can also download or print your schedule for reference. Schedule changes will be reflected here automatically.
                ''',
                'category_slug': 'academic-records',
                'order': 3
            },
            {
                'question': 'How do I check my attendance records?',
                'answer': '''
To view attendance information:

1. Log in to your student portal
2. Navigate to "Attendance" section
3. Select the period you want to review (daily, weekly, monthly)
4. View detailed attendance records by subject

Parents can monitor their children's attendance through the parent portal. Contact your teachers or academic office if you notice any discrepancies.
                ''',
                'category_slug': 'academic-records',
                'order': 4
            },
            {
                'question': 'How do I request an academic transcript?',
                'answer': '''
To request a transcript:

1. Log in to your account
2. Go to "Documents" > "Academic Records"
3. Select "Request Transcript"
4. Choose the format and delivery method
5. Submit your request with any required fees

Processing time is typically 3-5 business days. Official transcripts are sent directly to institutions or your mailing address.
                ''',
                'category_slug': 'academic-records',
                'order': 5
            },

            # Fees & Payments (existing + new)
            {
                'question': 'How can I view my fee statement and payment history?',
                'answer': '''
To access your financial information:

1. Log in to your account
2. Go to "Finance" or "Fees & Payments"
3. Select "Fee Statement" to see outstanding balances
4. Choose "Payment History" to view past transactions

All fees, payments, discounts, and outstanding balances are displayed here.
                ''',
                'category_slug': 'fees-payments',
                'order': 1
            },
            {
                'question': 'What payment methods are accepted?',
                'answer': '''
We accept the following payment methods:

**Online Payments**:
- Credit/Debit cards (Visa, MasterCard, American Express)
- Bank transfers
- Mobile money (M-Pesa, Airtel Money, etc.)
- Online banking

**Offline Payments**:
- Cash payments at school bursar's office
- Bank deposits (provide reference number when submitting proof)
- Cheques

All payments should include your student ID or reference number.
                ''',
                'category_slug': 'fees-payments',
                'order': 2
            },
            {
                'question': 'How do I pay school fees online?',
                'answer': '''
Online payment process:

1. Log in to your account
2. Go to "Finance" > "Make Payment"
3. Select the fee type and amount
4. Choose your payment method
5. Review and confirm payment details
6. Complete the transaction

You'll receive a payment confirmation and receipt via email. Processing time is usually instant for cards and 1-2 business days for bank transfers.
                ''',
                'category_slug': 'fees-payments',
                'order': 3
            },
            {
                'question': 'What if I have a payment dispute or need a refund?',
                'answer': '''
For payment issues:

1. Contact the bursar's office with your payment reference
2. Provide supporting documentation
3. Submit a formal request through the system or email

Refunds are processed within 14-21 business days after approval. All refund requests are reviewed by the finance department.
                ''',
                'category_slug': 'fees-payments',
                'order': 4
            },
            {
                'question': 'How do I apply for a fee waiver or scholarship?',
                'answer': '''
Fee waiver/scholarship process:

1. Log in to your account
2. Go to "Finance" > "Financial Aid"
3. Select "Apply for Waiver/Scholarship"
4. Fill out the application form with required details
5. Upload supporting documents
6. Submit your application

Applications are reviewed by the financial aid office. You'll be notified of the decision via email or through the system.
                ''',
                'category_slug': 'fees-payments',
                'order': 5
            },

            # System Usage (existing + new)
            {
                'question': 'How do I update my contact information?',
                'answer': '''
To update your contact details:

1. Log in to your account
2. Go to "Profile" or "Account Settings"
3. Select "Contact Information"
4. Update phone number, email, or address as needed
5. Save changes

Important contact updates (like emergency contacts) may require verification. Always keep your information current for important school communications.
                ''',
                'category_slug': 'system-usage',
                'order': 1
            },
            {
                'question': 'How do I download documents like transcripts or certificates?',
                'answer': '''
To download official documents:

1. Log in to your account
2. Go to "Documents" or "Downloads" section
3. Select the document type you need (transcript, certificate, etc.)
4. Choose the academic year/period
5. Click "Generate" or "Download"

Some documents may require approval before they become available for download.
                ''',
                'category_slug': 'system-usage',
                'order': 2
            },
            {
                'question': 'How do I report a technical issue with the system?',
                'answer': '''
To report a technical problem:

1. Contact support through the "Support" section
2. Select "Technical Issue" as the category
3. Provide detailed description including:
   - What you were trying to do
   - Error messages received
   - Browser and device information
   - Steps to reproduce the issue

Include screenshots if possible. Our technical team will respond within 24 hours.
                ''',
                'category_slug': 'system-usage',
                'order': 3
            },
            {
                'question': 'How do I use the mobile app?',
                'answer': '''
Using the mobile app:

1. Download from Google Play Store or Apple App Store
2. Log in with your school account credentials
3. Sets up notifications for important updates
4. Access all features available in the web version

The mobile app offers offline viewing for schedules and assignments.
                ''',
                'category_slug': 'system-usage',
                'order': 4
            },
            {
                'question': 'How do I export my data or reports?',
                'answer': '''
To export reports and data:

1. Navigate to the relevant section (Grades, Finance, etc.)
2. Click on "Export" or "Download Report"
3. Select your preferred format (PDF, Excel, CSV)
4. Choose date ranges and filters as needed
5. Click "Generate" and download

Exports are available for most reports and historical data.
                ''',
                'category_slug': 'system-usage',
                'order': 5
            },

            # Support & Communication (existing + new)
            {
                'question': 'How do I contact my teachers or academic advisors?',
                'answer': '''
Communication methods:

**Through the System**:
1. Log in to your account
2. Go to "Messages" or "Communication"
3. Select your teacher/advisor from the directory
4. Send your message

**Direct Contact**: Use email addresses or phone numbers provided by your school.

**Office Hours**: Visit teachers during their posted office hours for in-person discussions.
                ''',
                'category_slug': 'support-communication',
                'order': 1
            },
            {
                'question': 'Who do I contact for different types of support?',
                'answer': '''
Support contacts by category:

**Academic Issues**: Academic advisor or department head
**Technical Problems**: IT Support (available 24/7 for critical issues)
**Financial Concerns**: Bursar's office
**Medical/Health Issues**: School nurse or health services
**Disciplinary Matters**: Student affairs office
**General Support**: Student services or reception

Use the support ticketing system for faster, tracked assistance.
                ''',
                'category_slug': 'support-communication',
                'order': 2
            },
            {
                'question': 'How do I get emergency contact information?',
                'answer': '''
Emergency contacts:

**Within School Hours**:
- Main Office: Ext. 100
- Security: Ext. 111 (Emergency button on all phones)
- Nurse: Ext. 222

**Outside School Hours**:
- Emergency Services: Call local emergency number
- School Administration: Contact the principal's direct line

All emergency procedures are posted in common areas and available on the school website.
                ''',
                'category_slug': 'support-communication',
                'order': 3
            },

            # Library Services
            {
                'question': 'How do I search for books in the library?',
                'answer': '''
To search the library catalog:

1. Log in to your account
2. Go to "Library" section
3. Use the search bar with keywords, author, or title
4. Filter results by subject, type, or availability
5. Click on a book to see details and reserve/place holds

You can also browse books by category or view new acquisitions.
                ''',
                'category_slug': 'library-services',
                'order': 1
            },
            {
                'question': 'What are the library borrowing rules?',
                'answer': '''
Library borrowing policy:

- Books: 2 weeks for general, 1 week for reference
- Maximum books: 5 for students, 10 for staff
- Renewals: Up to 2 times online
- Fines: $0.50 per day for overdue books
- Holds: Reserve books online when they're checked out

Lost or damaged books must be replaced or paid for. Check your library account regularly.
                ''',
                'category_slug': 'library-services',
                'order': 2
            },

            # Health & Medical
            {
                'question': 'How do I schedule a health appointment?',
                'answer': '''
To schedule medical care:

1. Log in to your account
2. Go to "Health" > "Schedule Appointment"
3. Select the type of service needed
4. Choose available date and time
5. Submit your request

Emergency medical issues should be reported to the school nurse immediately. Parents will be notified for serious concerns.
                ''',
                'category_slug': 'health-medical',
                'order': 1
            },
            {
                'question': 'What medical services are available?',
                'answer': '''
Available health services:

- Daily health check-ups
- First aid and emergency response
- Immunization tracking
- Health education and counseling
- Chronic condition management
- Mental health support

Students requiring regular medication should register with the health office. All services are confidential.
                ''',
                'category_slug': 'health-medical',
                'order': 2
            },

            # Transportation
            {
                'question': 'How do I check bus routes and schedules?',
                'answer': '''
To view transportation information:

1. Log in to your account
2. Go to "Transportation" section
3. View assigned bus route and stops
4. Check daily schedule and any changes
5. Download route maps for reference

Route changes are updated in real-time. Contact transport office for route changes or special requests.
                ''',
                'category_slug': 'transportation',
                'order': 1
            },
            {
                'question': 'What should I do if I miss my bus?',
                'answer': '''
If you miss your assigned bus:

- Contact the transport office immediately
- Inform your parents/guardians
- Use alternative transportation if arranged
- Report to school office for late arrival procedures

Never leave campus with unauthorized individuals. Safety protocols must be followed.
                ''',
                'category_slug': 'transportation',
                'order': 2
            },

            # Hostel & Accommodation
            {
                'question': 'How do I apply for hostel accommodation?',
                'answer': '''
Hostel application process:

1. Log in to your account
2. Go to "Hostel" > "Apply for Accommodation"
3. Fill out the application form
4. Upload required documents (ID, medical certificate, etc.)
5. Submit application with hostel fees

Applications are processed on a first-come basis. Space is limited and allocated by merit.
                ''',
                'category_slug': 'hostel-accommodation',
                'order': 1
            },
            {
                'question': 'What are the hostel rules and regulations?',
                'answer': '''
Important hostel rules:

- Check-in/out: 6 AM - 10 PM for security
- Visitors: Only during designated hours with permission
- Curfew: Must be in rooms by specified time
- Cleanliness: Maintain personal and common areas
- Noise: Respect quiet hours during study times

Violation of rules may result in warnings or expulsion. Safety and security are top priorities.
                ''',
                'category_slug': 'hostel-accommodation',
                'order': 2
            },

            # Activities & Clubs
            {
                'question': 'How do I join a school club or activity?',
                'answer': '''
To join extracurricular activities:

1. Log in to your account
2. Go to "Activities" > "Browse Clubs"
3. View available sports, clubs, and societies
4. Click "Join" for activities of interest
5. Attend the first meeting or tryout

Some activities have auditions, trials, or limited membership. Check activity requirements.
                ''',
                'category_slug': 'activities-clubs',
                'order': 1
            },
            {
                'question': 'How do I view upcoming events and activities?',
                'answer': '''
To browse school events:

1. Go to "Activities" > "Events Calendar"
2. View events by date, type, or participation
3. Filter by sports events, cultural programs, etc.
4. Click on events for details and registration

Subscribe to notifications for your favorite activities and never miss important events.
                ''',
                'category_slug': 'activities-clubs',
                'order': 2
            },
        ]

        created_count = 0
        updated_count = 0

        for faq_data in faqs_data:
            # Get or create category
            category_slug = faq_data['category_slug']
            try:
                category = Category.objects.get(slug=category_slug)
            except Category.DoesNotExist:
                # Skip if category doesn't exist (shouldn't happen with our create_categories call)
                self.stdout.write(
                    self.style.WARNING(f'Category {category_slug} not found, skipping FAQ: {faq_data["question"][:50]}...')
                )
                continue

            # Check if FAQ already exists
            existing_faq = FAQ.objects.filter(
                question__iexact=faq_data['question'],
                category=category
            ).first()

            if existing_faq:
                # Update content if needed
                if existing_faq.answer.strip() != faq_data['answer'].strip():
                    existing_faq.answer = faq_data['answer'].strip()
                    existing_faq.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Updated FAQ: {faq_data["question"][:50]}...')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'FAQ already exists: {faq_data["question"][:50]}...')
                    )
            else:
                # Create new FAQ
                FAQ.objects.create(
                    question=faq_data['question'],
                    answer=faq_data['answer'].strip(),
                    category=category,
                    order=faq_data['order'],
                    is_published=True
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created FAQ: {faq_data["question"][:50]}...')
                )

        if created_count > 0 or updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {created_count} and updated {updated_count} FAQs.')
            )
            self.stdout.write(
                self.style.SUCCESS('You can now view the FAQs at /support/faq/')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('All FAQs already exist and are up to date.')
            )

    def create_categories(self):
        """Create the necessary categories for FAQs."""
        categories_data = [
            {'name': 'Account & Login', 'slug': 'account-login', 'description': 'Questions about user accounts, login, and authentication'},
            {'name': 'Academic Records', 'slug': 'academic-records', 'description': 'Questions about grades, courses, and academic information'},
            {'name': 'Fees & Payments', 'slug': 'fees-payments', 'description': 'Questions about school fees, payments, and financial matters'},
            {'name': 'System Usage', 'slug': 'system-usage', 'description': 'Questions about using the school management system'},
            {'name': 'Support & Communication', 'slug': 'support-communication', 'description': 'Questions about getting help and contacting school staff'},
            {'name': 'Library Services', 'slug': 'library-services', 'description': 'Questions about library resources and borrowing'},
            {'name': 'Health & Medical', 'slug': 'health-medical', 'description': 'Questions about school health services and medical care'},
            {'name': 'Transportation', 'slug': 'transportation', 'description': 'Questions about school transportation services'},
            {'name': 'Hostel & Accommodation', 'slug': 'hostel-accommodation', 'description': 'Questions about hostel facilities and accommodation'},
            {'name': 'Activities & Clubs', 'slug': 'activities-clubs', 'description': 'Questions about extracurricular activities and clubs'},
        ]

        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created category: {cat_data["name"]}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Category already exists: {cat_data["name"]}')
                )

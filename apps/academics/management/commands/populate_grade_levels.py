"""
Django management command to populate grade levels according to Nigerian and international education standards.

This command creates comprehensive grade levels for all education stages:
- Preschool (Nigerian Creche/Nursery + International Pre-K/Kindergarten)
- Elementary (Nigerian Primary + International Elementary)
- Middle School (Nigerian Junior Secondary + International Middle School)
- High School (Nigerian Senior Secondary + International High School)
- Undergraduate (University levels)
- Graduate (Masters, PhD)
- Postgraduate (Advanced degrees)
- Diploma/Certificate (Polytechnic, Professional certifications)

Usage:
    python manage.py populate_grade_levels
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.academics.models import GradeLevel


class Command(BaseCommand):
    help = 'Populate grade levels according to Nigerian and international education standards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing grade levels before populating',
        )
        parser.add_argument(
            '--nigerian-only',
            action='store_true',
            help='Only populate Nigerian standards',
        )
        parser.add_argument(
            '--international-only',
            action='store_true',
            help='Only populate international standards',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting grade levels population...')
        )

        if options['clear']:
            self.stdout.write('Clearing existing grade levels...')
            GradeLevel.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS('Existing grade levels cleared.')
            )

        try:
            with transaction.atomic():
                if options['nigerian_only']:
                    self._populate_nigerian_standards()
                elif options['international_only']:
                    self._populate_international_standards()
                else:
                    self._populate_nigerian_standards()
                    self._populate_international_standards()

                self._create_progression_links()

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully populated grade levels. Total: {GradeLevel.objects.count()}'
                )
            )

        except Exception as e:
            raise CommandError(f'Error populating grade levels: {e}')

    def _populate_nigerian_standards(self):
        """Populate Nigerian education standards."""
        self.stdout.write('Populating Nigerian education standards...')

        nigerian_levels = [
            # Preschool/Early Childhood Education
            {
                'name': 'Creche',
                'code': 'CR',
                'education_stage': 'preschool',
                'short_name': 'Creche',
                'description': 'Early childhood education for children aged 3-4 years',
                'typical_start_age': 3,
                'typical_end_age': 4,
                'is_entry_level': True,
            },
            {
                'name': 'Nursery 1',
                'code': 'N1',
                'education_stage': 'preschool',
                'short_name': 'Nursery 1',
                'description': 'First year of nursery education for children aged 4-5 years',
                'typical_start_age': 4,
                'typical_end_age': 5,
            },
            {
                'name': 'Nursery 2',
                'code': 'N2',
                'education_stage': 'preschool',
                'short_name': 'Nursery 2',
                'description': 'Second year of nursery education for children aged 5-6 years',
                'typical_start_age': 5,
                'typical_end_age': 6,
            },

            # Primary Education
            {
                'name': 'Primary 1',
                'code': 'P1',
                'education_stage': 'elementary',
                'short_name': 'Primary 1',
                'description': 'First year of primary education',
                'typical_start_age': 6,
                'typical_end_age': 7,
                'is_entry_level': True,
            },
            {
                'name': 'Primary 2',
                'code': 'P2',
                'education_stage': 'elementary',
                'short_name': 'Primary 2',
                'description': 'Second year of primary education',
                'typical_start_age': 7,
                'typical_end_age': 8,
            },
            {
                'name': 'Primary 3',
                'code': 'P3',
                'education_stage': 'elementary',
                'short_name': 'Primary 3',
                'description': 'Third year of primary education',
                'typical_start_age': 8,
                'typical_end_age': 9,
            },
            {
                'name': 'Primary 4',
                'code': 'P4',
                'education_stage': 'elementary',
                'short_name': 'Primary 4',
                'description': 'Fourth year of primary education',
                'typical_start_age': 9,
                'typical_end_age': 10,
            },
            {
                'name': 'Primary 5',
                'code': 'P5',
                'education_stage': 'elementary',
                'short_name': 'Primary 5',
                'description': 'Fifth year of primary education',
                'typical_start_age': 10,
                'typical_end_age': 11,
            },
            {
                'name': 'Primary 6',
                'code': 'P6',
                'education_stage': 'elementary',
                'short_name': 'Primary 6',
                'description': 'Sixth and final year of primary education',
                'typical_start_age': 11,
                'typical_end_age': 12,
            },

            # Junior Secondary School
            {
                'name': 'Junior Secondary School 1',
                'code': 'JSS1',
                'education_stage': 'middle_school',
                'short_name': 'JSS 1',
                'description': 'First year of junior secondary education',
                'typical_start_age': 12,
                'typical_end_age': 13,
                'is_entry_level': True,
            },
            {
                'name': 'Junior Secondary School 2',
                'code': 'JSS2',
                'education_stage': 'middle_school',
                'short_name': 'JSS 2',
                'description': 'Second year of junior secondary education',
                'typical_start_age': 13,
                'typical_end_age': 14,
            },
            {
                'name': 'Junior Secondary School 3',
                'code': 'JSS3',
                'education_stage': 'middle_school',
                'short_name': 'JSS 3',
                'description': 'Third and final year of junior secondary education',
                'typical_start_age': 14,
                'typical_end_age': 15,
            },

            # Senior Secondary School
            {
                'name': 'Senior Secondary School 1',
                'code': 'SSS1',
                'education_stage': 'high_school',
                'short_name': 'SSS 1',
                'description': 'First year of senior secondary education',
                'typical_start_age': 15,
                'typical_end_age': 16,
                'is_entry_level': True,
            },
            {
                'name': 'Senior Secondary School 2',
                'code': 'SSS2',
                'education_stage': 'high_school',
                'short_name': 'SSS 2',
                'description': 'Second year of senior secondary education',
                'typical_start_age': 16,
                'typical_end_age': 17,
            },
            {
                'name': 'Senior Secondary School 3',
                'code': 'SSS3',
                'education_stage': 'high_school',
                'short_name': 'SSS 3',
                'description': 'Third and final year of senior secondary education',
                'typical_start_age': 17,
                'typical_end_age': 18,
            },

            # University Undergraduate
            {
                'name': '100 Level',
                'code': '100L',
                'education_stage': 'undergraduate',
                'short_name': '100L',
                'description': 'First year of university undergraduate studies',
                'credit_hours': 30,
                'is_entry_level': True,
            },
            {
                'name': '200 Level',
                'code': '200L',
                'education_stage': 'undergraduate',
                'short_name': '200L',
                'description': 'Second year of university undergraduate studies',
                'credit_hours': 30,
            },
            {
                'name': '300 Level',
                'code': '300L',
                'education_stage': 'undergraduate',
                'short_name': '300L',
                'description': 'Third year of university undergraduate studies',
                'credit_hours': 30,
            },
            {
                'name': '400 Level',
                'code': '400L',
                'education_stage': 'undergraduate',
                'short_name': '400L',
                'description': 'Fourth year of university undergraduate studies',
                'credit_hours': 30,
            },
            {
                'name': '500 Level',
                'code': '500L',
                'education_stage': 'undergraduate',
                'short_name': '500L',
                'description': 'Fifth year of university undergraduate studies (for 5-year programs)',
                'credit_hours': 30,
            },

            # Polytechnic/National Diploma
            {
                'name': 'National Diploma 1',
                'code': 'ND1',
                'education_stage': 'diploma',
                'short_name': 'ND1',
                'description': 'First year of National Diploma program',
                'credit_hours': 30,
                'is_entry_level': True,
            },
            {
                'name': 'National Diploma 2',
                'code': 'ND2',
                'education_stage': 'diploma',
                'short_name': 'ND2',
                'description': 'Second year of National Diploma program',
                'credit_hours': 30,
            },
            {
                'name': 'Higher National Diploma 1',
                'code': 'HND1',
                'education_stage': 'diploma',
                'short_name': 'HND1',
                'description': 'First year of Higher National Diploma program',
                'credit_hours': 30,
            },
            {
                'name': 'Higher National Diploma 2',
                'code': 'HND2',
                'education_stage': 'diploma',
                'short_name': 'HND2',
                'description': 'Second year of Higher National Diploma program',
                'credit_hours': 30,
            },
        ]

        for level_data in nigerian_levels:
            level, created = GradeLevel.objects.get_or_create(
                code=level_data['code'],
                defaults=level_data
            )
            if created:
                self.stdout.write(f'  Created: {level.name} ({level.code})')

    def _populate_international_standards(self):
        """Populate international education standards (US system)."""
        self.stdout.write('Populating international education standards...')

        international_levels = [
            # Preschool/Early Childhood Education
            {
                'name': 'Pre-Kindergarten',
                'code': 'PK',
                'education_stage': 'preschool',
                'short_name': 'Pre-K',
                'description': 'Pre-kindergarten for children aged 3-4 years',
                'typical_start_age': 3,
                'typical_end_age': 4,
                'is_entry_level': True,
            },
            {
                'name': 'Kindergarten',
                'code': 'K',
                'education_stage': 'preschool',
                'short_name': 'K',
                'description': 'Kindergarten for children aged 4-5 years',
                'typical_start_age': 4,
                'typical_end_age': 5,
            },

            # Elementary School
            {
                'name': 'Grade 1',
                'code': 'G1',
                'education_stage': 'elementary',
                'short_name': 'Grade 1',
                'description': 'First grade of elementary school',
                'typical_start_age': 6,
                'typical_end_age': 7,
                'is_entry_level': True,
            },
            {
                'name': 'Grade 2',
                'code': 'G2',
                'education_stage': 'elementary',
                'short_name': 'Grade 2',
                'description': 'Second grade of elementary school',
                'typical_start_age': 7,
                'typical_end_age': 8,
            },
            {
                'name': 'Grade 3',
                'code': 'G3',
                'education_stage': 'elementary',
                'short_name': 'Grade 3',
                'description': 'Third grade of elementary school',
                'typical_start_age': 8,
                'typical_end_age': 9,
            },
            {
                'name': 'Grade 4',
                'code': 'G4',
                'education_stage': 'elementary',
                'short_name': 'Grade 4',
                'description': 'Fourth grade of elementary school',
                'typical_start_age': 9,
                'typical_end_age': 10,
            },
            {
                'name': 'Grade 5',
                'code': 'G5',
                'education_stage': 'elementary',
                'short_name': 'Grade 5',
                'description': 'Fifth grade of elementary school',
                'typical_start_age': 10,
                'typical_end_age': 11,
            },

            # Middle School
            {
                'name': 'Grade 6',
                'code': 'G6',
                'education_stage': 'middle_school',
                'short_name': 'Grade 6',
                'description': 'Sixth grade of middle school',
                'typical_start_age': 11,
                'typical_end_age': 12,
                'is_entry_level': True,
            },
            {
                'name': 'Grade 7',
                'code': 'G7',
                'education_stage': 'middle_school',
                'short_name': 'Grade 7',
                'description': 'Seventh grade of middle school',
                'typical_start_age': 12,
                'typical_end_age': 13,
            },
            {
                'name': 'Grade 8',
                'code': 'G8',
                'education_stage': 'middle_school',
                'short_name': 'Grade 8',
                'description': 'Eighth grade of middle school',
                'typical_start_age': 13,
                'typical_end_age': 14,
            },

            # High School
            {
                'name': 'Grade 9',
                'code': 'G9',
                'education_stage': 'high_school',
                'short_name': 'Grade 9',
                'description': 'Freshman year of high school',
                'typical_start_age': 14,
                'typical_end_age': 15,
                'is_entry_level': True,
            },
            {
                'name': 'Grade 10',
                'code': 'G10',
                'education_stage': 'high_school',
                'short_name': 'Grade 10',
                'description': 'Sophomore year of high school',
                'typical_start_age': 15,
                'typical_end_age': 16,
            },
            {
                'name': 'Grade 11',
                'code': 'G11',
                'education_stage': 'high_school',
                'short_name': 'Grade 11',
                'description': 'Junior year of high school',
                'typical_start_age': 16,
                'typical_end_age': 17,
            },
            {
                'name': 'Grade 12',
                'code': 'G12',
                'education_stage': 'high_school',
                'short_name': 'Grade 12',
                'description': 'Senior year of high school',
                'typical_start_age': 17,
                'typical_end_age': 18,
            },

            # College/University Undergraduate
            {
                'name': 'Freshman Year',
                'code': 'FR',
                'education_stage': 'undergraduate',
                'short_name': 'Freshman',
                'description': 'First year of college/university',
                'credit_hours': 30,
                'is_entry_level': True,
            },
            {
                'name': 'Sophomore Year',
                'code': 'SO',
                'education_stage': 'undergraduate',
                'short_name': 'Sophomore',
                'description': 'Second year of college/university',
                'credit_hours': 30,
            },
            {
                'name': 'Junior Year',
                'code': 'JR',
                'education_stage': 'undergraduate',
                'short_name': 'Junior',
                'description': 'Third year of college/university',
                'credit_hours': 30,
            },
            {
                'name': 'Senior Year',
                'code': 'SR',
                'education_stage': 'undergraduate',
                'short_name': 'Senior',
                'description': 'Fourth year of college/university',
                'credit_hours': 30,
            },

            # Graduate School
            {
                'name': 'Masters Year 1',
                'code': 'M1',
                'education_stage': 'graduate',
                'short_name': 'Masters 1',
                'description': 'First year of Masters program',
                'credit_hours': 24,
                'is_entry_level': True,
            },
            {
                'name': 'Masters Year 2',
                'code': 'M2',
                'education_stage': 'graduate',
                'short_name': 'Masters 2',
                'description': 'Second year of Masters program',
                'credit_hours': 24,
            },
            {
                'name': 'Doctor of Philosophy Year 1',
                'code': 'PhD1',
                'education_stage': 'postgraduate',
                'short_name': 'PhD 1',
                'description': 'First year of PhD program',
                'credit_hours': 12,
                'is_entry_level': True,
            },
            {
                'name': 'Doctor of Philosophy Year 2',
                'code': 'PhD2',
                'education_stage': 'postgraduate',
                'short_name': 'PhD 2',
                'description': 'Second year of PhD program',
                'credit_hours': 12,
            },
            {
                'name': 'Doctor of Philosophy Year 3',
                'code': 'PhD3',
                'education_stage': 'postgraduate',
                'short_name': 'PhD 3',
                'description': 'Third year of PhD program',
                'credit_hours': 12,
            },
            {
                'name': 'Doctor of Philosophy Year 4',
                'code': 'PhD4',
                'education_stage': 'postgraduate',
                'short_name': 'PhD 4',
                'description': 'Fourth year of PhD program',
                'credit_hours': 12,
            },

            # Professional Certifications
            {
                'name': 'Certificate Program',
                'code': 'CERT',
                'education_stage': 'diploma',
                'short_name': 'Certificate',
                'description': 'Professional certificate program',
                'credit_hours': 15,
                'is_entry_level': True,
            },
            {
                'name': 'Diploma Program',
                'code': 'DIP',
                'education_stage': 'diploma',
                'short_name': 'Diploma',
                'description': 'Professional diploma program',
                'credit_hours': 30,
            },
            {
                'name': 'Advanced Diploma',
                'code': 'ADIP',
                'education_stage': 'diploma',
                'short_name': 'Adv Diploma',
                'description': 'Advanced professional diploma program',
                'credit_hours': 45,
            },
        ]

        for level_data in international_levels:
            level, created = GradeLevel.objects.get_or_create(
                code=level_data['code'],
                defaults=level_data
            )
            if created:
                self.stdout.write(f'  Created: {level.name} ({level.code})')

    def _create_progression_links(self):
        """Create progression links between grade levels."""
        self.stdout.write('Creating progression links...')

        # Define progression order by education stage
        progressions = {
            'preschool': ['CR', 'N1', 'N2', 'PK', 'K'],
            'elementary': ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'G1', 'G2', 'G3', 'G4', 'G5'],
            'middle_school': ['JSS1', 'JSS2', 'JSS3', 'G6', 'G7', 'G8'],
            'high_school': ['SSS1', 'SSS2', 'SSS3', 'G9', 'G10', 'G11', 'G12'],
            'undergraduate': ['100L', '200L', '300L', '400L', '500L', 'FR', 'SO', 'JR', 'SR'],
            'graduate': ['M1', 'M2'],
            'postgraduate': ['PhD1', 'PhD2', 'PhD3', 'PhD4'],
            'diploma': ['ND1', 'ND2', 'HND1', 'HND2', 'CERT', 'DIP', 'ADIP'],
        }

        # Set final levels
        final_levels = ['N2', 'K', 'P6', 'G5', 'JSS3', 'G8', 'SSS3', 'G12', '500L', 'SR', 'M2', 'PhD4', 'ADIP']
        GradeLevel.objects.filter(code__in=final_levels).update(is_final_level=True)

        # Create progression links
        for stage, codes in progressions.items():
            for i, code in enumerate(codes):
                try:
                    level = GradeLevel.objects.get(code=code)
                    if i < len(codes) - 1:
                        next_code = codes[i + 1]
                        try:
                            next_level = GradeLevel.objects.get(code=next_code)
                            level.next_level = next_level
                            level.save()
                            self.stdout.write(f'  Linked: {level.code} -> {next_level.code}')
                        except GradeLevel.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(f'  Warning: Next level {next_code} not found for {code}')
                            )
                except GradeLevel.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'  Warning: Level {code} not found')
                    )

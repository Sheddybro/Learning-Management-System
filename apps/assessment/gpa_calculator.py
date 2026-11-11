"""
GPA Calculator Utility
Simple GPA/CGPA calculation utilities based on the clue system
"""
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from django.db.models import Q, Sum, F
from .models import Result, ResultSubject, Grade


class GPACalculator:
    """
    Utility class for calculating GPA and CGPA
    """

    @staticmethod
    def calculate_student_gpa(
        student,
        semester: Optional[str] = None,
        level: Optional[str] = None
    ) -> Tuple[Decimal, Dict]:
        """
        Calculate GPA for a student for a specific semester/level

        Args:
            student: Student instance
            semester: Semester to calculate GPA for (optional)
            level: Academic level to calculate GPA for (optional)

        Returns:
            Tuple of (GPA, details_dict)
        """
        # Build query for results
        query = Q(student=student)

        if semester:
            query &= Q(exam_type__name__icontains='semester') | Q(exam_type__name__icontains=semester)

        if level:
            query &= Q(academic_class__level=level)

        results = Result.objects.filter(query).select_related(
            'exam_type', 'academic_class', 'grade'
        ).prefetch_related('subject_marks__subject', 'subject_marks__grade')

        if not results.exists():
            return Decimal('0.00'), {
                'total_points': 0,
                'total_credits': 0,
                'results_count': 0,
                'subjects': []
            }

        total_points = Decimal('0.00')
        total_credits = Decimal('0.00')
        subject_details = []

        for result in results:
            # Use subject marks if available, otherwise use overall result
            if result.subject_marks.exists():
                for subject_mark in result.subject_marks.all():
                    credit = getattr(subject_mark.subject, 'credit', 1)  # Default to 1 if no credit field
                    grade_point = subject_mark.grade.grade_point if subject_mark.grade else Decimal('0.00')

                    subject_points = Decimal(credit) * grade_point
                    total_points += subject_points
                    total_credits += Decimal(credit)

                    subject_details.append({
                        'subject': subject_mark.subject.name,
                        'credit': credit,
                        'grade': subject_mark.grade.grade if subject_mark.grade else 'N/A',
                        'grade_point': grade_point,
                        'points': subject_points
                    })
            else:
                # Fallback to overall result
                # Estimate credits based on number of subjects (simplified)
                estimated_credits = result.subject_marks.count() or 1
                grade_point = result.grade.grade_point if result.grade else Decimal('0.00')

                subject_points = Decimal(estimated_credits) * grade_point
                total_points += subject_points
                total_credits += Decimal(estimated_credits)

                subject_details.append({
                    'subject': f"Overall - {result.exam_type.name}",
                    'credit': estimated_credits,
                    'grade': result.grade.grade if result.grade else 'N/A',
                    'grade_point': grade_point,
                    'points': subject_points
                })

        gpa = total_points / total_credits if total_credits > 0 else Decimal('0.00')

        return round(gpa, 2), {
            'total_points': total_points,
            'total_credits': total_credits,
            'results_count': results.count(),
            'subjects': subject_details
        }

    @staticmethod
    def calculate_student_cgpa(student) -> Tuple[Decimal, Dict]:
        """
        Calculate Cumulative GPA (CGPA) for a student across all semesters

        Args:
            student: Student instance

        Returns:
            Tuple of (CGPA, details_dict)
        """
        # Get all results for the student
        results = Result.objects.filter(student=student).select_related(
            'exam_type', 'academic_class', 'grade'
        ).prefetch_related('subject_marks__subject', 'subject_marks__grade')

        if not results.exists():
            return Decimal('0.00'), {
                'total_points': 0,
                'total_credits': 0,
                'results_count': 0,
                'semesters': []
            }

        total_points = Decimal('0.00')
        total_credits = Decimal('0.00')
        semester_details = []

        # Group results by semester/level
        semester_results = {}
        for result in results:
            semester_key = f"{result.academic_class.level} - {result.exam_type.name}"
            if semester_key not in semester_results:
                semester_results[semester_key] = []
            semester_results[semester_key].append(result)

        # Calculate GPA for each semester
        for semester_key, semester_result_list in semester_results.items():
            semester_points = Decimal('0.00')
            semester_credits = Decimal('0.00')
            semester_subjects = []

            for result in semester_result_list:
                # Use subject marks if available
                if result.subject_marks.exists():
                    for subject_mark in result.subject_marks.all():
                        credit = getattr(subject_mark.subject, 'credit', 1)
                        grade_point = subject_mark.grade.grade_point if subject_mark.grade else Decimal('0.00')

                        subject_points = Decimal(credit) * grade_point
                        semester_points += subject_points
                        semester_credits += Decimal(credit)

                        semester_subjects.append({
                            'subject': subject_mark.subject.name,
                            'credit': credit,
                            'grade': subject_mark.grade.grade if subject_mark.grade else 'N/A',
                            'grade_point': grade_point,
                            'points': subject_points
                        })
                else:
                    # Fallback to overall result
                    estimated_credits = result.subject_marks.count() or 1
                    grade_point = result.grade.grade_point if result.grade else Decimal('0.00')

                    subject_points = Decimal(estimated_credits) * grade_point
                    semester_points += subject_points
                    semester_credits += Decimal(estimated_credits)

                    semester_subjects.append({
                        'subject': f"Overall - {result.exam_type.name}",
                        'credit': estimated_credits,
                        'grade': result.grade.grade if result.grade else 'N/A',
                        'grade_point': grade_point,
                        'points': subject_points
                    })

            semester_gpa = semester_points / semester_credits if semester_credits > 0 else Decimal('0.00')

            semester_details.append({
                'semester': semester_key,
                'gpa': round(semester_gpa, 2),
                'points': semester_points,
                'credits': semester_credits,
                'subjects': semester_subjects
            })

            total_points += semester_points
            total_credits += semester_credits

        cgpa = total_points / total_credits if total_credits > 0 else Decimal('0.00')

        return round(cgpa, 2), {
            'total_points': total_points,
            'total_credits': total_credits,
            'results_count': results.count(),
            'semesters': semester_details
        }

    @staticmethod
    def get_grade_from_percentage(percentage: float, grading_system=None) -> Optional[Grade]:
        """
        Get grade based on percentage score

        Args:
            percentage: Percentage score (0-100)
            grading_system: GradingSystem instance (optional)

        Returns:
            Grade instance or None
        """
        if grading_system:
            grades = Grade.objects.filter(grading_system=grading_system)
        else:
            # Use first active grading system
            from .models import GradingSystem
            active_system = GradingSystem.objects.filter(is_active=True).first()
            if active_system:
                grades = active_system.grades.all()
            else:
                return None

        for grade in grades.order_by('-min_mark'):
            if percentage >= float(grade.min_mark):
                return grade

        return None

    @staticmethod
    def get_gpa_classification(gpa: Decimal) -> str:
        """
        Get GPA classification based on GPA value

        Args:
            gpa: GPA value

        Returns:
            Classification string
        """
        if gpa >= Decimal('3.60'):
            return "First Class"
        elif gpa >= Decimal('3.00'):
            return "Second Class Upper"
        elif gpa >= Decimal('2.50'):
            return "Second Class Lower"
        elif gpa >= Decimal('2.00'):
            return "Third Class"
        elif gpa >= Decimal('1.00'):
            return "Pass"
        else:
            return "Fail"


# Convenience functions
def calculate_gpa(student, semester=None, level=None) -> Decimal:
    """
    Convenience function to calculate GPA
    """
    calculator = GPACalculator()
    gpa, _ = calculator.calculate_student_gpa(student, semester, level)
    return gpa


def calculate_cgpa(student) -> Decimal:
    """
    Convenience function to calculate CGPA
    """
    calculator = GPACalculator()
    cgpa, _ = calculator.calculate_student_cgpa(student)
    return cgpa


def get_gpa_details(student, semester=None, level=None) -> Dict:
    """
    Convenience function to get GPA details
    """
    calculator = GPACalculator()
    _, details = calculator.calculate_student_gpa(student, semester, level)
    return details


def get_cgpa_details(student) -> Dict:
    """
    Convenience function to get CGPA details
    """
    calculator = GPACalculator()
    _, details = calculator.calculate_student_cgpa(student)
    return details

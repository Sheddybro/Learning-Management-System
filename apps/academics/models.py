# apps/academics/models.py

from django.db import models
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    FileExtensionValidator,
)
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import CoreBaseModel, GlobalBaseModel, AddressModel, ContactModel


class AcademicSession(CoreBaseModel):
    """
    Model for managing academic sessions/years.
    """

    def progress_percentage(self):
        """Calculate session progress percentage."""
        from django.utils import timezone

        today = timezone.now().date()

        if today < self.start_date:
            return 0
        elif today > self.end_date:
            return 100

        total_days = (self.end_date - self.start_date).days
        days_passed = (today - self.start_date).days

        if total_days > 0:
            return min(100, int((days_passed / total_days) * 100))
        return 0

    name = models.CharField(_("session name"), max_length=100)
    number_of_semesters = models.PositiveSmallIntegerField(
        _("number of semesters"),
        choices=[(2, _("Two Semesters")), (3, _("Three Semesters"))],
        default=2,
        help_text=_("Specify if the school year has 2 or 3 semesters."),
        db_index=True,
    )
    term_number = models.PositiveSmallIntegerField(
        _("term/semester number"),
        choices=[
            (1, _("First Semester")),
            (2, _("Second Semester")),
            (3, _("Third Semester")),
        ],
        null=True,
        blank=True,
        help_text=_(
            "Set to 1, 2 or 3 for term/semester-based schools; leave null for whole-session models."
        ),
        db_index=True,
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))
    is_current = models.BooleanField(_("is current session"), default=False)

    class Meta:
        verbose_name = _("Academic Session")
        verbose_name_plural = _("Academic Sessions")
        ordering = ["-start_date"]
        # constraints = [
        #     models.CheckConstraint(
        #         check=models.Q(end_date__gt=models.F('start_date')),
        #         name='end_date_after_start_date'
        #     ),
        #     models.CheckConstraint(
        #         check=models.Q(term_number__isnull=True) | models.Q(term_number__lte=models.F('number_of_semesters')),
        #         name='term_number_within_semesters_range'
        #     )
        # ]

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.end_date <= self.start_date:
            raise ValidationError(_("End date must be after start date."))

        if self.term_number is not None and self.term_number > self.number_of_semesters:
            raise ValidationError(
                _(
                    "Term number cannot exceed the number of semesters configured for this session."
                )
            )

    def save(self, *args, **kwargs):
        """
        Ensure only one session can be marked as current.
        """
        if self.is_current:
            # Set all other sessions to not current
            AcademicSession.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)

    @property
    def semester_name(self):
        """Return the human-readable semester name."""
        if self.term_number == 1:
            return _("First Semester")
        elif self.term_number == 2:
            return _("Second Semester")
        elif self.term_number == 3:
            return _("Third Semester")
        return _("Full Session")


class Department(CoreBaseModel):
    """
    Academic departments (Science, Arts, Commerce, etc.)
    """

    name = models.CharField(_("department name"), max_length=100, unique=True)
    code = models.CharField(_("department code"), max_length=10, unique=True)
    description = models.TextField(_("description"), blank=True)
    head_of_department = models.ForeignKey(
        "Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_departments",
        verbose_name=_("head of department"),
    )
    established_date = models.DateField(_("established date"), null=True, blank=True)

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name", "code"]),
        ]

    def __str__(self):
        return self.name


class Subject(CoreBaseModel):
    """
    Academic subjects taught in the school
    """

    class SubjectType(models.TextChoices):
        CORE = "core", _("Core")
        ELECTIVE = "elective", _("Elective")

    name = models.CharField(_("subject name"), max_length=100)
    code = models.CharField(_("subject code"), max_length=20, unique=True)
    subject_type = models.CharField(
        _("subject type"),
        max_length=20,
        choices=SubjectType.choices,
        default=SubjectType.CORE,
    )
    description = models.TextField(_("description"), blank=True)
    credits = models.PositiveIntegerField(_("credits"), default=1)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="subjects",
        verbose_name=_("department"),
    )
    is_active = models.BooleanField(_("is active"), default=True)
    prerequisites = models.ManyToManyField(
        "self", symmetrical=False, blank=True, verbose_name=_("prerequisites")
    )

    class Meta:
        verbose_name = _("Subject")
        verbose_name_plural = _("Subjects")
        ordering = ["department", "name"]
        indexes = [
            models.Index(fields=["code", "is_active"]),
            models.Index(fields=["department", "subject_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class GradeLevel(GlobalBaseModel):
    """
    Educational grade/level system supporting K-12, college, and university
    """

    class EducationStage(models.TextChoices):
        PRESCHOOL = "preschool", _("Preschool")
        ELEMENTARY = "elementary", _("Elementary School")
        MIDDLE_SCHOOL = "middle_school", _("Middle School")
        HIGH_SCHOOL = "high_school", _("High School")
        UNDERGRADUATE = "undergraduate", _("Undergraduate")
        GRADUATE = "graduate", _("Graduate")
        POSTGRADUATE = "postgraduate", _("Postgraduate")
        DIPLOMA = "diploma", _("Diploma/Certificate")

    class GradeType(models.TextChoices):
        YEAR = "year", _("Year Level")
        GRADE = "grade", _("Grade Level")
        SEMESTER = "semester", _("Semester")
        TRIMESTER = "trimester", _("Trimester")
        QUARTER = "quarter", _("Quarter")

    name = models.CharField(_("grade name"), max_length=100)
    code = models.CharField(_("grade code"), max_length=20, unique=True)
    education_stage = models.CharField(
        _("education stage"), max_length=20, choices=EducationStage.choices
    )
    grade_type = models.CharField(
        _("grade type"),
        max_length=20,
        choices=GradeType.choices,
        default=GradeType.YEAR,
    )
    short_name = models.CharField(
        _("short name"),
        max_length=20,
        blank=True,
        help_text=_('Abbreviated name (e.g., "G1", "Y2", "S1")'),
    )
    description = models.TextField(_("description"), blank=True)

    # Age range (mainly for school levels)
    typical_start_age = models.PositiveIntegerField(
        _("typical start age"),
        null=True,
        blank=True,
        help_text=_("Typical age when students start this level"),
    )
    typical_end_age = models.PositiveIntegerField(
        _("typical end age"),
        null=True,
        blank=True,
        help_text=_("Typical age when students complete this level"),
    )

    # Academic credits (mainly for college/university)
    credit_hours = models.PositiveIntegerField(
        _("credit hours"), default=0, help_text=_("Typical credit hours for this level")
    )

    # Financial
    base_tuition_fee = models.DecimalField(
        _("base tuition fee"), max_digits=10, decimal_places=2, default=0.00
    )

    # Progression
    is_entry_level = models.BooleanField(
        _("is entry level"),
        default=False,
        help_text=_("First level in this education stage"),
    )
    is_final_level = models.BooleanField(
        _("is final level"),
        default=False,
        help_text=_("Final level in this education stage"),
    )
    next_level = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="previous_levels",
        verbose_name=_("next level"),
        help_text=_("The level students typically progress to after this one"),
    )

    class Meta:
        verbose_name = _("Grade Level")
        verbose_name_plural = _("Grade Levels")
        ordering = ["education_stage", "code"]
        indexes = [
            models.Index(fields=["education_stage", "code"]),
            models.Index(fields=["grade_type", "education_stage"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        if self.typical_start_age and self.typical_end_age:
            if self.typical_start_age >= self.typical_end_age:
                raise ValidationError(
                    _("Typical start age must be less than typical end age.")
                )

        if self.next_level and self.next_level == self:
            raise ValidationError(_("A level cannot be the next level of itself."))

    @property
    def display_name(self):
        """Return formatted display name."""
        if self.short_name:
            return f"{self.name} ({self.short_name})"
        return self.name

    @property
    def is_tertiary_level(self):
        """Check if this is a tertiary education level."""
        return self.education_stage in [
            self.EducationStage.UNDERGRADUATE,
            self.EducationStage.GRADUATE,
            self.EducationStage.POSTGRADUATE,
            self.EducationStage.DIPLOMA,
        ]

    @property
    def is_school_level(self):
        """Check if this is a school level (not tertiary)."""
        return self.education_stage in [
            self.EducationStage.PRESCHOOL,
            self.EducationStage.ELEMENTARY,
            self.EducationStage.MIDDLE_SCHOOL,
            self.EducationStage.HIGH_SCHOOL,
        ]


class Class(CoreBaseModel):
    """
    Specific classes (Grade 10 Regular, Grade 11 Honors, etc.)
    """

    class ClassType(models.TextChoices):
        REGULAR = "regular", _("Regular")
        HONORS = "honors", _("Honors")
        SPECIAL_NEEDS = "special_needs", _("Special Needs")

    name = models.CharField(_("class name"), max_length=100)
    code = models.CharField(_("class code"), max_length=20, unique=True)
    grade_level = models.ForeignKey(
        GradeLevel,
        on_delete=models.CASCADE,
        related_name="classes",
        verbose_name=_("grade level"),
        null=True,
        blank=True,
    )
    class_type = models.CharField(
        _("class type"),
        max_length=20,
        choices=ClassType.choices,
        default=ClassType.REGULAR,
    )
    capacity = models.PositiveIntegerField(_("maximum capacity"), default=40)
    class_teacher = models.ForeignKey(
        "academics.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homeroom_classes",
        verbose_name=_("class teacher"),
    )
    room_number = models.CharField(_("room number"), max_length=20, blank=True)
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="classes",
        verbose_name=_("academic session"),
    )

    class Meta:
        verbose_name = _("Class")
        verbose_name_plural = _("Classes")
        ordering = ["grade_level__name", "name"]
        unique_together = ["grade_level", "class_type", "academic_session"]
        indexes = [
            models.Index(fields=["grade_level", "class_type"]),
            models.Index(fields=["class_teacher", "academic_session"]),
        ]

    def __str__(self):
        return self.name

    @property
    def current_student_count(self):
        """Return current number of students in this class."""
        return self.enrollments.filter(
            status="active", academic_session=self.academic_session
        ).count()

    @property
    def available_seats(self):
        """Return number of available seats."""
        return self.capacity - self.current_student_count

    def is_full(self):
        """Check if class has reached capacity."""
        return self.current_student_count >= self.capacity

    @property
    def subjects(self):
        """Get subjects assigned to this class."""
        return Subject.objects.filter(
            subject_assignments__class_assigned=self,
            subject_assignments__academic_session=self.academic_session,
        ).distinct()


class Student(CoreBaseModel, AddressModel, ContactModel):
    """
    Student profile extending the core User model
    """

    class BloodGroup(models.TextChoices):
        A_POSITIVE = "a+", _("A+")
        A_NEGATIVE = "a-", _("A-")
        B_POSITIVE = "b+", _("B+")
        B_NEGATIVE = "b-", _("B-")
        AB_POSITIVE = "ab+", _("AB+")
        AB_NEGATIVE = "ab-", _("AB-")
        O_POSITIVE = "o+", _("O+")
        O_NEGATIVE = "o-", _("O-")

    class StudentType(models.TextChoices):
        REGULAR = "regular", _("Regular")
        TRANSFER = "transfer", _("Transfer")
        REPEATER = "repeater", _("Repeater")
        INTERNATIONAL = "international", _("International")

    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="student_profile",
        verbose_name=_("user account"),
    )
    student_id = models.CharField(
        _("student ID"), max_length=20, unique=True, db_index=True
    )
    admission_number = models.CharField(
        _("admission number"), max_length=20, unique=True
    )
    admission_date = models.DateField(_("admission date"))
    date_of_birth = models.DateField(_("date of birth"))
    place_of_birth = models.CharField(_("place of birth"), max_length=100, blank=True)
    gender = models.CharField(
        _("gender"),
        max_length=10,
        choices=[("male", _("Male")), ("female", _("Female")), ("other", _("Other"))],
    )
    blood_group = models.CharField(
        _("blood group"), max_length=3, choices=BloodGroup.choices, blank=True
    )
    nationality = models.CharField(_("nationality"), max_length=50, default="")
    religion = models.CharField(_("religion"), max_length=50, blank=True)
    student_type = models.CharField(
        _("student type"),
        max_length=20,
        choices=StudentType.choices,
        default=StudentType.REGULAR,
    )
    is_boarder = models.BooleanField(_("is boarder"), default=False)
    has_special_needs = models.BooleanField(_("has special needs"), default=False)
    special_needs_description = models.TextField(
        _("special needs description"), blank=True
    )
    previous_school = models.CharField(_("previous school"), max_length=200, blank=True)
    photo = models.ImageField(
        _("student photo"), upload_to="students/photos/", null=True, blank=True
    )

    # Department (for tertiary education students)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
        verbose_name=_("department"),
        help_text=_("Primary department for tertiary education students"),
    )

    # Parent/Guardian Information
    father_name = models.CharField(_("father name"), max_length=100, blank=True)
    father_occupation = models.CharField(
        _("father occupation"), max_length=100, blank=True
    )
    father_phone = models.CharField(_("father phone"), max_length=20, blank=True)
    father_email = models.EmailField(_("father email"), blank=True)

    mother_name = models.CharField(_("mother name"), max_length=100, blank=True)
    mother_occupation = models.CharField(
        _("mother occupation"), max_length=100, blank=True
    )
    mother_phone = models.CharField(_("mother phone"), max_length=20, blank=True)
    mother_email = models.EmailField(_("mother email"), blank=True)

    guardian_name = models.CharField(_("guardian name"), max_length=100, blank=True)
    guardian_relation = models.CharField(
        _("guardian relation"), max_length=50, blank=True
    )
    guardian_occupation = models.CharField(
        _("guardian occupation"), max_length=100, blank=True
    )
    guardian_phone = models.CharField(_("guardian phone"), max_length=20, blank=True)
    guardian_email = models.EmailField(_("guardian email"), blank=True)

    class Meta:
        verbose_name = _("Student")
        verbose_name_plural = _("Students")
        ordering = ["student_id"]
        indexes = [
            models.Index(fields=["student_id", "status"]),
            models.Index(fields=["admission_number"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

    def save(self, *args, **kwargs):
        """Auto-generate student ID if not provided."""
        if not self.student_id:
            self.student_id = self.generate_student_id()
        super().save(*args, **kwargs)

    def generate_student_id(self):
        """Generate unique student ID using SequenceGenerator per institution."""
        from apps.core.models import SequenceGenerator

        sequence, created = SequenceGenerator.objects.get_or_create(
            sequence_type=SequenceGenerator.SequenceType.STUDENT_ID,
            institution=self.institution,
            defaults={"prefix": f"{self.institution.code}-STU-", "padding": 3},
        )
        return sequence.get_next_number()

    @property
    def current_class(self):
        """Get current class enrollment for active session."""
        current_enrollment = self.enrollments.filter(
            status="active", academic_session__is_current=True
        ).first()
        return current_enrollment.class_enrolled if current_enrollment else None

    @property
    def current_department(self):
        """Get current department enrollment for active session."""
        current_enrollment = self.enrollments.filter(
            status="active", academic_session__is_current=True
        ).first()
        return current_enrollment.department if current_enrollment else None

    @property
    def age(self):
        """Calculate current age from date of birth."""
        from datetime import date

        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    def get_today_attendance(self):
        """Get today's attendance record for this student."""
        from django.utils import timezone
        from apps.attendance.models import DailyAttendance

        today = timezone.now().date()
        current_session = self.enrollments.filter(
            status="active", academic_session__is_current=True
        ).first()

        if current_session:
            return DailyAttendance.objects.filter(
                student=self,
                date=today,
                attendance_session__academic_session=current_session.academic_session,
            ).first()
        return None


class Teacher(CoreBaseModel, AddressModel, ContactModel):
    """
    Teacher profile extending the core User model
    """

    class TeacherType(models.TextChoices):
        FULL_TIME = "full_time", _("Full Time")
        PART_TIME = "part_time", _("Part Time")
        VISITING = "visiting", _("Visiting")
        CONTRACT = "contract", _("Contract")

    class Qualification(models.TextChoices):
        BACHELORS = "bachelors", _("Bachelors")
        MASTERS = "masters", _("Masters")
        PHD = "phd", _("PhD")
        DIPLOMA = "diploma", _("Diploma")
        CERTIFICATION = "certification", _("Certification")

    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="teacher_profile",
        verbose_name=_("user account"),
    )
    teacher_id = models.CharField(
        _("teacher ID"), max_length=20, unique=True, db_index=True
    )
    employee_id = models.CharField(_("employee ID"), max_length=20, unique=True)
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)
    gender = models.CharField(
        _("gender"),
        max_length=10,
        choices=[("male", _("Male")), ("female", _("Female")), ("other", _("Other"))],
    )
    teacher_type = models.CharField(
        _("teacher type"),
        max_length=20,
        choices=TeacherType.choices,
        default=TeacherType.FULL_TIME,
    )
    qualification = models.CharField(
        _("highest qualification"),
        max_length=20,
        choices=Qualification.choices,
        default=Qualification.BACHELORS,
    )
    specialization = models.CharField(_("specialization"), max_length=100, blank=True)
    joining_date = models.DateField(_("joining date"))
    experience_years = models.PositiveIntegerField(_("years of experience"), default=0)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teachers",
        verbose_name=_("department"),
    )
    is_class_teacher = models.BooleanField(_("is class teacher"), default=False)
    is_system_admin = models.BooleanField(_("is system admin teacher"), default=False)
    bio = models.TextField(_("biography"), blank=True)
    photo = models.ImageField(
        _("teacher photo"), upload_to="teachers/photos/", null=True, blank=True
    )

    class Meta:
        verbose_name = _("Teacher")
        verbose_name_plural = _("Teachers")
        ordering = ["teacher_id"]
        indexes = [
            models.Index(fields=["teacher_id", "status"]),
            models.Index(fields=["department", "teacher_type"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.teacher_id})"

    @property
    def subjects_taught(self):
        """Get subjects currently taught by this teacher."""
        return Subject.objects.filter(
            subject_assignments__teacher=self,
            subject_assignments__academic_session__is_current=True,
        ).distinct()

    @property
    def current_classes(self):
        """Get classes currently taught by this teacher."""
        return Class.objects.filter(
            subject_assignments__teacher=self,
            subject_assignments__academic_session__is_current=True,
        ).distinct()


class Enrollment(CoreBaseModel):
    """
    Student enrollment in classes for academic sessions
    """

    class EnrollmentStatus(models.TextChoices):
        ACTIVE = "active", _("Active")
        COMPLETED = "completed", _("Completed")
        TRANSFERRED = "transferred", _("Transferred")
        WITHDRAWN = "withdrawn", _("Withdrawn")
        SUSPENDED = "suspended", _("Suspended")

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name=_("student"),
    )
    class_enrolled = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name=_("class"),
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name=_("academic session"),
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrollments",
        verbose_name=_("department"),
        help_text=_("Department for tertiary education enrollments"),
    )
    enrollment_date = models.DateField(_("enrollment date"))
    enrollment_status = models.CharField(
        _("enrollment status"),
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE,
    )
    roll_number = models.PositiveIntegerField(_("roll number"))
    remarks = models.TextField(_("remarks"), blank=True)

    class Meta:
        verbose_name = _("Enrollment")
        verbose_name_plural = _("Enrollments")
        ordering = ["class_enrolled", "roll_number"]
        unique_together = [
            ["student", "academic_session"],
            ["class_enrolled", "roll_number", "academic_session"],
        ]
        indexes = [
            models.Index(fields=["student", "enrollment_status"]),
            models.Index(fields=["class_enrolled", "academic_session"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.class_enrolled} ({self.academic_session})"

    def clean(self):
        if self.academic_session and self.enrollment_date:
            if self.enrollment_date < self.academic_session.start_date:
                raise ValidationError(
                    _("Enrollment date cannot be before academic session start date.")
                )
            if self.enrollment_date > self.academic_session.end_date:
                raise ValidationError(
                    _("Enrollment date cannot be after academic session end date.")
                )


class SubjectAssignment(CoreBaseModel):
    """
    Assignment of teachers to subjects in specific classes
    """

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="subject_assignments",
        verbose_name=_("teacher"),
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="subject_assignments",
        verbose_name=_("subject"),
    )
    class_assigned = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="subject_assignments",
        verbose_name=_("class"),
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="subject_assignments",
        verbose_name=_("academic session"),
    )
    periods_per_week = models.PositiveIntegerField(
        _("periods per week"),
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
    is_primary_teacher = models.BooleanField(_("is primary teacher"), default=True)

    class Meta:
        verbose_name = _("Subject Assignment")
        verbose_name_plural = _("Subject Assignments")
        unique_together = ["teacher", "subject", "class_assigned", "academic_session"]
        ordering = ["class_assigned", "subject"]
        indexes = [
            models.Index(fields=["teacher", "academic_session"]),
            models.Index(fields=["class_assigned", "subject"]),
        ]

    def __str__(self):
        return f"{self.teacher} - {self.subject} - {self.class_assigned}"


class AcademicRecord(CoreBaseModel):
    """
    Comprehensive academic history for students
    """

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="academic_records",
        verbose_name=_("student"),
    )
    class_enrolled = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="academic_records",
        verbose_name=_("class"),
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="academic_records",
        verbose_name=_("academic session"),
    )
    overall_grade = models.CharField(_("overall grade"), max_length=5, blank=True)
    total_marks = models.DecimalField(
        _("total marks"), max_digits=6, decimal_places=2, null=True, blank=True
    )
    percentage = models.DecimalField(
        _("percentage"), max_digits=5, decimal_places=2, null=True, blank=True
    )
    rank_in_class = models.PositiveIntegerField(
        _("rank in class"), null=True, blank=True
    )
    total_students_in_class = models.PositiveIntegerField(
        _("total students in class"), null=True, blank=True
    )
    remarks = models.TextField(_("remarks"), blank=True)
    promoted_to_class = models.ForeignKey(
        Class,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotions_received",
        verbose_name=_("promoted to class"),
    )
    promotion_date = models.DateField(_("promotion date"), null=True, blank=True)

    class Meta:
        verbose_name = _("Academic Record")
        verbose_name_plural = _("Academic Records")
        unique_together = ["student", "class_enrolled", "academic_session"]
        ordering = ["academic_session", "class_enrolled"]
        indexes = [
            models.Index(fields=["student", "academic_session"]),
            models.Index(fields=["class_enrolled", "academic_session"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.class_enrolled} - {self.academic_session}"


class Timetable(CoreBaseModel):
    """
    Comprehensive school timetable management with room allocation and special periods
    """

    class DayOfWeek(models.TextChoices):
        MONDAY = "monday", _("Monday")
        TUESDAY = "tuesday", _("Tuesday")
        WEDNESDAY = "wednesday", _("Wednesday")
        THURSDAY = "thursday", _("Thursday")
        FRIDAY = "friday", _("Friday")
        SATURDAY = "saturday", _("Saturday")
        SUNDAY = "sunday", _("Sunday")

    class PeriodType(models.TextChoices):
        REGULAR_CLASS = "regular_class", _("Regular Class")
        BREAK = "break", _("Break")
        LUNCH = "lunch", _("Lunch")
        ASSEMBLY = "assembly", _("Assembly")
        SPORTS = "sports", _("Sports")
        ACTIVITY = "activity", _("Activity")
        EXAM = "exam", _("Exam")
        MEETING = "meeting", _("Meeting")

    class RoomType(models.TextChoices):
        CLASSROOM = "classroom", _("Classroom")
        LABORATORY = "laboratory", _("Laboratory")
        COMPUTER_LAB = "computer_lab", _("Computer Lab")
        SCIENCE_LAB = "science_lab", _("Science Lab")
        ART_ROOM = "art_room", _("Art Room")
        MUSIC_ROOM = "music_room", _("Music Room")
        LIBRARY = "library", _("Library")
        AUDITORIUM = "auditorium", _("Auditorium")
        SPORTS_HALL = "sports_hall", _("Sports Hall")
        CONFERENCE_ROOM = "conference_room", _("Conference Room")

    # Basic scheduling information
    class_assigned = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="timetables",
        verbose_name=_("class"),
        null=True,
        blank=True,  # Allow null for school-wide events
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="timetables",
        verbose_name=_("academic session"),
    )
    day_of_week = models.CharField(
        _("day of week"), max_length=10, choices=DayOfWeek.choices
    )
    period_number = models.PositiveIntegerField(
        _("period number"),
        validators=[
            MinValueValidator(1),
            MaxValueValidator(15),
        ],  # Increased for longer days
    )
    period_type = models.CharField(
        _("period type"),
        max_length=20,
        choices=PeriodType.choices,
        default=PeriodType.REGULAR_CLASS,
    )
    start_time = models.TimeField(_("start time"))
    end_time = models.TimeField(_("end time"))

    # Academic content (nullable for non-class periods)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
        verbose_name=_("subject"),
        null=True,
        blank=True,
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
        verbose_name=_("teacher"),
        null=True,
        blank=True,
    )

    # Room allocation (embedded room information)
    room_number = models.CharField(_("room number"), max_length=20, blank=True)
    room_name = models.CharField(
        _("room name"),
        max_length=100,
        blank=True,
        help_text=_('Optional descriptive name (e.g., "Main Science Lab")'),
    )
    room_type = models.CharField(
        _("room type"),
        max_length=20,
        choices=RoomType.choices,
        default=RoomType.CLASSROOM,
        blank=True,
    )
    room_capacity = models.PositiveIntegerField(
        _("room capacity"),
        validators=[MinValueValidator(1), MaxValueValidator(500)],
        null=True,
        blank=True,
    )
    room_building = models.CharField(
        _("building"),
        max_length=100,
        blank=True,
        help_text=_("Building name or designation"),
    )
    room_floor = models.CharField(
        _("floor"),
        max_length=10,
        blank=True,
        help_text=_("Floor number or designation"),
    )
    room_facilities = models.TextField(
        _("facilities"),
        blank=True,
        help_text=_(
            'Comma-separated list of facilities (e.g., "Projector, AC, Whiteboard")'
        ),
    )

    # Additional metadata
    title = models.CharField(
        _("period title"),
        max_length=200,
        blank=True,
        help_text=_("Custom title for breaks, assemblies, etc."),
    )
    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Additional details about this period"),
    )
    is_shared_event = models.BooleanField(
        _("is shared event"),
        default=False,
        help_text=_("Event shared across multiple classes (e.g., assembly)"),
    )
    shared_with_classes = models.ManyToManyField(
        Class,
        related_name="shared_timetable_events",
        blank=True,
        verbose_name=_("shared with classes"),
        help_text=_("Other classes participating in this shared event"),
    )
    color_code = models.CharField(
        _("color code"),
        max_length=7,
        default="#3498db",
        help_text=_("Hex color for display (e.g., #3498db)"),
    )
    is_published = models.BooleanField(
        _("is published"),
        default=True,
        help_text=_("Whether this entry is visible on public timetables"),
    )
    is_room_available = models.BooleanField(
        _("is room available"),
        default=True,
        help_text=_("Whether the room is available for scheduling"),
    )

    class Meta:
        verbose_name = _("Timetable")
        verbose_name_plural = _("Timetables")
        ordering = ["class_assigned", "day_of_week", "period_number"]
        unique_together = [
            ["class_assigned", "day_of_week", "period_number", "academic_session"],
            ["teacher", "day_of_week", "period_number", "academic_session"],
            ["room_number", "day_of_week", "period_number", "academic_session"],
        ]
        indexes = [
            models.Index(fields=["class_assigned", "academic_session"]),
            models.Index(fields=["teacher", "academic_session"]),
            models.Index(fields=["room_number", "academic_session"]),
            models.Index(fields=["day_of_week", "period_type"]),
            models.Index(fields=["is_published", "academic_session"]),
            models.Index(fields=["room_type", "is_room_available"]),
            models.Index(fields=["room_building", "room_floor"]),
        ]

    def __str__(self):
        if self.period_type != self.PeriodType.REGULAR_CLASS:
            return f"{self.title} - {self.day_of_week} - {self.start_time}"
        return (
            f"{self.class_assigned} - {self.day_of_week} - Period {self.period_number}"
        )

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError(_("End time must be after start time."))

        # Validate room capacity for class assignments
        if (
            self.class_assigned
            and self.room_capacity
            and self.period_type == self.PeriodType.REGULAR_CLASS
        ):
            if self.class_assigned.current_student_count > self.room_capacity:
                raise ValidationError(
                    _("Room capacity is less than class student count.")
                )

        # Validate subject/teacher requirements for regular classes
        if self.period_type == self.PeriodType.REGULAR_CLASS:
            if not self.subject:
                raise ValidationError(_("Subject is required for regular classes."))
            if not self.teacher:
                raise ValidationError(_("Teacher is required for regular classes."))
            if not self.class_assigned:
                raise ValidationError(_("Class is required for regular classes."))

        # Validate room information for physical locations
        if self.period_type == self.PeriodType.REGULAR_CLASS and not self.room_number:
            raise ValidationError(_("Room number is required for regular classes."))

    @property
    def display_title(self):
        """Get appropriate display title based on period type."""
        if self.period_type != self.PeriodType.REGULAR_CLASS:
            return self.title or self.get_period_type_display()
        return self.subject.name

    @property
    def duration_minutes(self):
        """Calculate duration in minutes."""
        if self.start_time and self.end_time:
            from datetime import datetime

            start_dt = datetime.combine(datetime.today(), self.start_time)
            end_dt = datetime.combine(datetime.today(), self.end_time)
            return int((end_dt - start_dt).total_seconds() / 60)
        return 0

    @property
    def is_active_today(self):
        """Check if this timetable entry is for today."""
        from datetime import datetime

        return self.day_of_week == datetime.now().strftime("%A").lower()

    @property
    def display_room_info(self):
        """Get formatted room information."""
        if not self.room_number:
            return "Online/Virtual"

        room_parts = []
        if self.room_building:
            room_parts.append(self.room_building)
        if self.room_floor:
            room_parts.append(f"Floor {self.room_floor}")
        room_parts.append(f"Room {self.room_number}")

        if self.room_name:
            room_parts.append(f"({self.room_name})")

        return ", ".join(room_parts)

    @property
    def room_utilization(self):
        """Calculate current room utilization for this period."""
        if not self.room_number or not self.room_capacity or not self.class_assigned:
            return None

        student_count = self.class_assigned.current_student_count
        utilization = (student_count / self.room_capacity) * 100
        return round(utilization, 1)

    @property
    def is_room_overcrowded(self):
        """Check if room is over capacity."""
        utilization = self.room_utilization
        return utilization > 100 if utilization else False

    @classmethod
    def get_school_wide_timetable(cls, academic_session):
        """Get complete school timetable for a session."""
        return (
            cls.objects.filter(academic_session=academic_session, is_published=True)
            .select_related("class_assigned", "subject", "teacher")
            .prefetch_related("shared_with_classes")
        )

    @classmethod
    def get_room_schedule(cls, room_number, academic_session):
        """Get complete schedule for a specific room."""
        return cls.objects.filter(
            room_number=room_number,
            academic_session=academic_session,
            is_published=True,
        ).order_by("day_of_week", "start_time")

    @classmethod
    def get_room_utilization_stats(cls, room_number, academic_session):
        """Get room utilization statistics."""
        from django.db.models import Count

        timetable_entries = cls.objects.filter(
            room_number=room_number, academic_session=academic_session
        )

        total_periods = timetable_entries.count()
        days_used = timetable_entries.values("day_of_week").distinct().count()

        return {
            "total_periods": total_periods,
            "days_used": days_used,
            "utilization_rate": (
                (total_periods / (days_used * 10)) * 100 if days_used > 0 else 0
            ),
        }

    @classmethod
    def create_break_period(
        cls,
        class_assigned,
        day_of_week,
        period_number,
        start_time,
        end_time,
        title="Break",
    ):
        """Helper to create break periods."""
        return cls.objects.create(
            class_assigned=class_assigned,
            academic_session=class_assigned.academic_session,
            day_of_week=day_of_week,
            period_number=period_number,
            start_time=start_time,
            end_time=end_time,
            period_type=cls.PeriodType.BREAK,
            title=title,
            color_code="#95a5a6",
        )

    @classmethod
    def get_todays_schedule_for_user(cls, user):
        """Get today's schedule for a user (student or teacher)."""
        from datetime import datetime

        today = datetime.now().strftime("%A").lower()

        if hasattr(user, "student_profile"):
            current_class = user.student_profile.current_class
            return cls.objects.filter(
                class_assigned=current_class,
                day_of_week=today,
                academic_session__is_current=True,
                is_published=True,
            ).order_by("period_number")

        elif hasattr(user, "teacher_profile"):
            teacher = user.teacher_profile
            return cls.objects.filter(
                teacher=teacher,
                day_of_week=today,
                academic_session__is_current=True,
                is_published=True,
            ).order_by("period_number")

        return cls.objects.none()


class AttendanceSchedule(CoreBaseModel):
    """
    Attendance schedule and rules for classes with flexible timing
    """

    class SessionType(models.TextChoices):
        MORNING = "morning", _("Morning Session")
        AFTERNOON = "afternoon", _("Afternoon Session")
        EVENING = "evening", _("Evening Session")
        FULL_DAY = "full_day", _("Full Day")
        CUSTOM = "custom", _("Custom Timing")

    class_assigned = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="attendance_schedules",
        verbose_name=_("class"),
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="attendance_schedules",
        verbose_name=_("academic session"),
    )
    session_type = models.CharField(
        _("session type"),
        max_length=20,
        choices=SessionType.choices,
        default=SessionType.MORNING,
    )
    session_start_time = models.TimeField(_("session start time"))
    session_end_time = models.TimeField(_("session end time"))
    late_mark_minutes = models.PositiveIntegerField(
        _("late mark threshold (minutes)"), default=15
    )
    early_departure_minutes = models.PositiveIntegerField(
        _("early departure threshold (minutes)"), default=30
    )
    has_break = models.BooleanField(_("has break period"), default=False)
    break_start_time = models.TimeField(_("break start time"), null=True, blank=True)
    break_end_time = models.TimeField(_("break end time"), null=True, blank=True)

    class Meta:
        verbose_name = _("Attendance Schedule")
        verbose_name_plural = _("Attendance Schedules")
        unique_together = ["class_assigned", "academic_session"]
        ordering = ["class_assigned"]

    def __str__(self):
        return f"Attendance Schedule - {self.class_assigned} ({self.get_session_type_display()})"

    def clean(self):
        # Validate session times
        if self.session_start_time >= self.session_end_time:
            raise ValidationError(_("Session end time must be after start time."))

        # Validate break times if break is enabled
        if self.has_break:
            if not self.break_start_time or not self.break_end_time:
                raise ValidationError(
                    _("Break times are required when break period is enabled.")
                )
            if self.break_start_time >= self.break_end_time:
                raise ValidationError(_("Break end time must be after start time."))
            if not (
                self.session_start_time
                <= self.break_start_time
                <= self.session_end_time
            ):
                raise ValidationError(_("Break must occur within session time."))
            if not (
                self.session_start_time <= self.break_end_time <= self.session_end_time
            ):
                raise ValidationError(_("Break must occur within session time."))

    @property
    def display_session_timing(self):
        """Get formatted session timing for display."""
        start = self.session_start_time.strftime("%I:%M %p")
        end = self.session_end_time.strftime("%I:%M %p")
        return f"{self.get_session_type_display()}: {start} - {end}"

    @property
    def is_morning_session(self):
        """Check if this is a morning session."""
        return self.session_type == self.SessionType.MORNING

    @property
    def is_afternoon_session(self):
        """Check if this is an afternoon session."""
        return self.session_type == self.SessionType.AFTERNOON

    @property
    def is_evening_session(self):
        """Check if this is an evening session."""
        return self.session_type == self.SessionType.EVENING

    @property
    def is_full_day(self):
        """Check if this is a full day session."""
        return self.session_type == self.SessionType.FULL_DAY

    @classmethod
    def get_suggested_timings(cls, session_type):
        """Get suggested timings for common session types."""
        suggestions = {
            cls.SessionType.MORNING: {
                "start": "08:00",
                "end": "12:30",
                "late_minutes": 15,
                "early_minutes": 30,
            },
            cls.SessionType.AFTERNOON: {
                "start": "13:00",
                "end": "17:30",
                "late_minutes": 10,
                "early_minutes": 30,
            },
            cls.SessionType.EVENING: {
                "start": "18:00",
                "end": "21:00",
                "late_minutes": 5,
                "early_minutes": 15,
            },
            cls.SessionType.FULL_DAY: {
                "start": "08:30",
                "end": "15:30",
                "late_minutes": 15,
                "early_minutes": 45,
            },
        }
        return suggestions.get(session_type, {})


class ClassMaterial(CoreBaseModel):
    class MaterialType(models.TextChoices):
        TEXTBOOK = "textbook", _("Textbook")
        WORKSHEET = "worksheet", _("Worksheet")
        PRESENTATION = "presentation", _("Presentation")
        VIDEO = "video", _("Video")
        AUDIO = "audio", _("Audio")
        DOCUMENT = "document", _("Document")
        LINK = "link", _("Link")
        QUIZ = "quiz", _("Quiz")
        ASSIGNMENT = "assignment", _("Assignment")
        SYLLABUS = "syllabus", _("Syllabus")
        OTHER = "other", _("Other")

    class AccessLevel(models.TextChoices):
        PUBLIC = "public", _("All Students")
        RESTRICTED = "restricted", _("Specific Students")
        PRIVATE = "private", _("Teacher Only")

    # Basic Information
    title = models.CharField(_("material title"), max_length=200)
    material_type = models.CharField(
        _("material type"),
        max_length=20,
        choices=MaterialType.choices,
        default=MaterialType.DOCUMENT,
    )
    description = models.TextField(_("description"), blank=True)

    # File Management
    file = models.FileField(
        _("file"),
        upload_to="class_materials/%Y/%m/%d/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "doc",
                    "docx",
                    "ppt",
                    "pptx",
                    "xlsx",
                    "jpg",
                    "jpeg",
                    "png",
                    "mp4",
                    "mp3",
                    "zip",
                    "txt",
                ]
            )
        ],
    )
    file_size = models.PositiveIntegerField(
        _("file size in bytes"), null=True, blank=True
    )
    external_url = models.URLField(_("external URL"), blank=True)
    thumbnail = models.ImageField(
        _("thumbnail"), upload_to="material_thumbnails/", null=True, blank=True
    )

    # Version Control
    version = models.PositiveIntegerField(_("version"), default=1)
    parent_material = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="revisions",
        verbose_name=_("parent material"),
    )
    is_latest_version = models.BooleanField(_("is latest version"), default=True)
    change_log = models.TextField(_("change log"), blank=True)

    # Academic Context
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="materials",
        verbose_name=_("subject"),
    )
    class_assigned = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="materials",
        verbose_name=_("class"),
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="materials",
        verbose_name=_("teacher"),
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="materials",
        verbose_name=_("academic session"),
    )

    # Access Control
    access_level = models.CharField(
        _("access level"),
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.PUBLIC,
    )
    allowed_students = models.ManyToManyField(
        Student,
        blank=True,
        related_name="allowed_materials",
        verbose_name=_("allowed students"),
    )
    requires_acknowledgment = models.BooleanField(
        _("requires student acknowledgment"), default=False
    )

    # Publishing & Organization
    is_public = models.BooleanField(_("is public to students"), default=True)
    is_featured = models.BooleanField(_("is featured material"), default=False)
    publish_date = models.DateTimeField(_("publish date"), default=timezone.now)
    expiry_date = models.DateTimeField(_("expiry date"), null=True, blank=True)
    tags = models.CharField(_("tags"), max_length=500, blank=True)
    display_order = models.PositiveIntegerField(_("display order"), default=0)

    # Usage Tracking
    download_count = models.PositiveIntegerField(_("download count"), default=0)
    view_count = models.PositiveIntegerField(_("view count"), default=0)
    last_downloaded = models.DateTimeField(_("last downloaded"), null=True, blank=True)
    last_viewed = models.DateTimeField(_("last viewed"), null=True, blank=True)

    class Meta:
        verbose_name = _("Class Material")
        verbose_name_plural = _("Class Materials")
        ordering = ["display_order", "-publish_date", "subject"]
        indexes = [
            models.Index(fields=["subject", "class_assigned"]),
            models.Index(fields=["teacher", "publish_date"]),
            models.Index(fields=["material_type", "is_public"]),
            models.Index(fields=["access_level", "expiry_date"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.subject}"

    def clean(self):
        """Validate model constraints."""
        if not self.file and not self.external_url:
            raise ValidationError(_("Either file or external URL must be provided."))

        if self.expiry_date and self.expiry_date <= timezone.now():
            raise ValidationError(_("Expiry date must be in the future."))

        if self.parent_material and self.parent_material == self:
            raise ValidationError(_("A material cannot be its own parent."))

    def save(self, *args, **kwargs):
        """Auto-calculate file size and handle versioning."""
        if self.file:
            self.file_size = self.file.size

        # If this is a new version, update the previous version
        if self.parent_material and self.parent_material.is_latest_version:
            self.parent_material.is_latest_version = False
            self.parent_material.save()

        super().save(*args, **kwargs)

    @property
    def file_extension(self):
        """Get file extension for display."""
        if self.file:
            return self.file.name.split(".")[-1].upper()
        return None

    @property
    def is_expired(self):
        """Check if material has expired."""
        if self.expiry_date:
            return timezone.now() > self.expiry_date
        return False

    @property
    def is_active(self):
        """Check if material is currently active."""
        return self.is_public and not self.is_expired

    def increment_download_count(self):
        """Increment download count and update timestamp."""
        self.download_count += 1
        self.last_downloaded = timezone.now()
        self.save(update_fields=["download_count", "last_downloaded"])

    def increment_view_count(self):
        """Increment view count and update timestamp."""
        self.view_count += 1
        self.last_viewed = timezone.now()
        self.save(update_fields=["view_count", "last_viewed"])

    def get_absolute_url(self):
        """Return the URL for this material's detail view."""
        from django.urls import reverse

        return reverse("academics:material_detail", kwargs={"pk": self.pk})


class BehaviorRecord(CoreBaseModel):
    class BehaviorType(models.TextChoices):
        POSITIVE = "positive", _("Positive")
        NEGATIVE = "negative", _("Negative")
        NEUTRAL = "neutral", _("Neutral")

    class Severity(models.TextChoices):
        LOW = "low", _("Low")
        MEDIUM = "medium", _("Medium")
        HIGH = "high", _("High")
        CRITICAL = "critical", _("Critical")

    class IncidentCategory(models.TextChoices):
        ACADEMIC = "academic", _("Academic")
        BEHAVIORAL = "behavioral", _("Behavioral")
        ATTENDANCE = "attendance", _("Attendance")
        BULLYING = "bullying", _("Bullying")
        PROPERTY_DAMAGE = "property_damage", _("Property Damage")
        DRESS_CODE = "dress_code", _("Dress Code Violation")
        ELECTRONICS = "electronics", _("Electronics Misuse")
        RESPECT = "respect", _("Respect/Disrespect")
        SAFETY = "safety", _("Safety Violation")
        OTHER = "other", _("Other")

    class ConsequenceType(models.TextChoices):
        WARNING = "warning", _("Verbal Warning")
        WRITTEN_WARNING = "written_warning", _("Written Warning")
        DETENTION = "detention", _("Detention")
        SUSPENSION = "suspension", _("Suspension")
        PARENT_MEETING = "parent_meeting", _("Parent Meeting")
        COUNSELING = "counseling", _("Counseling Referral")
        COMMUNITY_SERVICE = "community_service", _("Community Service")
        RESTITUTION = "restitution", _("Restitution")
        OTHER = "other", _("Other")

    # Core Incident Information
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="behavior_records",
        verbose_name=_("student"),
    )
    behavior_type = models.CharField(
        _("behavior type"),
        max_length=20,
        choices=BehaviorType.choices,
        default=BehaviorType.NEUTRAL,
    )
    severity = models.CharField(
        _("severity"), max_length=20, choices=Severity.choices, default=Severity.LOW
    )
    incident_category = models.CharField(
        _("incident category"),
        max_length=30,
        choices=IncidentCategory.choices,
        default=IncidentCategory.BEHAVIORAL,
    )
    title = models.CharField(_("incident title"), max_length=200)
    description = models.TextField(_("detailed description"))

    # Incident Details
    incident_date = models.DateField(_("incident date"))
    incident_time = models.TimeField(_("incident time"), null=True, blank=True)
    location = models.CharField(_("incident location"), max_length=100, blank=True)

    # Reporting & Evidence
    reported_by = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="reported_incidents",
        verbose_name=_("reported by"),
    )
    reported_date = models.DateTimeField(_("reported date"), auto_now_add=True)
    evidence_files = models.FileField(
        _("evidence files"),
        upload_to="behavior_evidence/%Y/%m/%d/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "jpg",
                    "jpeg",
                    "png",
                    "mp4",
                    "avi",
                    "doc",
                    "docx",
                ]
            )
        ],
    )
    evidence_description = models.TextField(_("evidence description"), blank=True)

    # Witness Information
    has_witnesses = models.BooleanField(_("has witnesses"), default=False)
    witnesses = models.TextField(_("witnesses"), blank=True)
    witness_statements = models.TextField(_("witness statements"), blank=True)

    # Action & Consequences
    action_taken = models.TextField(_("action taken"), blank=True)
    consequence_type = models.CharField(
        _("consequence type"),
        max_length=30,
        choices=ConsequenceType.choices,
        blank=True,
    )
    consequence_duration = models.CharField(
        _("consequence duration"), max_length=100, blank=True
    )
    action_deadline = models.DateField(_("action deadline"), null=True, blank=True)
    action_completed = models.BooleanField(_("action completed"), default=False)

    # Follow-up & Resolution
    follow_up_required = models.BooleanField(_("follow up required"), default=False)
    follow_up_date = models.DateField(_("follow up date"), null=True, blank=True)
    next_follow_up_date = models.DateField(
        _("next follow-up date"), null=True, blank=True
    )
    follow_up_notes = models.TextField(_("follow-up notes"), blank=True)
    resolution = models.TextField(_("resolution"), blank=True)
    is_resolved = models.BooleanField(_("is resolved"), default=False)
    resolution_date = models.DateField(_("resolution date"), null=True, blank=True)

    # Parent Communication
    parent_notified = models.BooleanField(_("parent notified"), default=False)
    parent_notification_date = models.DateField(
        _("parent notification date"), null=True, blank=True
    )
    parent_response = models.TextField(_("parent response"), blank=True)
    parent_meeting_scheduled = models.BooleanField(
        _("parent meeting scheduled"), default=False
    )
    parent_meeting_date = models.DateField(
        _("parent meeting date"), null=True, blank=True
    )

    # Escalation
    escalated_to = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalated_behavior_cases",
        verbose_name=_("escalated to"),
    )
    escalation_date = models.DateField(_("escalation date"), null=True, blank=True)
    escalation_reason = models.TextField(_("escalation reason"), blank=True)

    # Additional Metadata
    case_number = models.CharField(
        _("case number"),
        max_length=20,
        unique=True,
        blank=True,
        help_text=_("Auto-generated case number"),
    )
    tags = models.CharField(_("tags"), max_length=500, blank=True)

    class Meta:
        verbose_name = _("Behavior Record")
        verbose_name_plural = _("Behavior Records")
        ordering = ["-incident_date", "-created_at"]
        indexes = [
            models.Index(fields=["student", "behavior_type"]),
            models.Index(fields=["incident_date", "severity"]),
            models.Index(fields=["incident_category", "is_resolved"]),
            models.Index(fields=["reported_by", "incident_date"]),
            models.Index(fields=["case_number"]),
        ]

    def __str__(self):
        return f"{self.case_number}: {self.student} - {self.title}"

    def clean(self):
        """Enhanced validation"""
        if self.follow_up_date and self.incident_date:
            if self.follow_up_date < self.incident_date:
                raise ValidationError(
                    _("Follow-up date cannot be before incident date.")
                )

        if self.action_deadline and self.incident_date:
            if self.action_deadline < self.incident_date:
                raise ValidationError(
                    _("Action deadline cannot be before incident date.")
                )

        if self.resolution_date and self.incident_date:
            if self.resolution_date < self.incident_date:
                raise ValidationError(
                    _("Resolution date cannot be before incident date.")
                )

    def save(self, *args, **kwargs):
        """Auto-generate case number and manage status"""
        if not self.case_number:
            self.case_number = self.generate_case_number()

        # Auto-set resolution date when marked as resolved
        if self.is_resolved and not self.resolution_date:
            self.resolution_date = timezone.now().date()

        super().save(*args, **kwargs)

    def generate_case_number(self):
        """Generate unique case number"""
        from django.utils import timezone

        year = timezone.now().strftime("%Y")
        last_case = (
            BehaviorRecord.objects.filter(case_number__startswith=f"BH-{year}-")
            .order_by("-case_number")
            .first()
        )

        if last_case:
            last_number = int(last_case.case_number.split("-")[-1])
            new_number = last_number + 1
        else:
            new_number = 1

        return f"BH-{year}-{new_number:04d}"

    @property
    def days_since_incident(self):
        """Calculate days since incident"""
        from datetime import date

        if self.incident_date:
            delta = date.today() - self.incident_date
            return delta.days
        return None

    @property
    def requires_immediate_attention(self):
        """Check if record requires immediate attention"""
        return (
            self.severity in [self.Severity.HIGH, self.Severity.CRITICAL]
            and not self.is_resolved
        )

    @property
    def is_overdue_follow_up(self):
        """Check if follow-up is overdue"""
        from datetime import date

        return (
            self.follow_up_required
            and self.follow_up_date
            and self.follow_up_date < date.today()
            and not self.is_resolved
        )

    def escalate_case(self, escalated_to_user, reason):
        """Escalate the case to another staff member"""
        self.escalated_to = escalated_to_user
        self.escalation_date = timezone.now().date()
        self.escalation_reason = reason
        self.save()

    def mark_parent_notified(self):
        """Mark parent as notified with current date"""
        self.parent_notified = True
        self.parent_notification_date = timezone.now().date()
        self.save()


class Achievement(CoreBaseModel):
    """
    Student achievements and awards
    """

    class AchievementType(models.TextChoices):
        ACADEMIC = "academic", _("Academic")
        SPORTS = "sports", _("Sports")
        ARTS = "arts", _("Arts")
        LEADERSHIP = "leadership", _("Leadership")
        COMMUNITY_SERVICE = "community_service", _("Community Service")
        OTHER = "other", _("Other")

    class AchievementLevel(models.TextChoices):
        SCHOOL = "school", _("School Level")
        DISTRICT = "district", _("District Level")
        STATE = "state", _("State Level")
        NATIONAL = "national", _("National Level")
        INTERNATIONAL = "international", _("International Level")

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="achievements",
        verbose_name=_("student"),
    )
    achievement_type = models.CharField(
        _("achievement type"),
        max_length=20,
        choices=AchievementType.choices,
        default=AchievementType.ACADEMIC,
    )
    achievement_level = models.CharField(
        _("achievement level"),
        max_length=20,
        choices=AchievementLevel.choices,
        default=AchievementLevel.SCHOOL,
    )
    title = models.CharField(_("achievement title"), max_length=200)
    description = models.TextField(_("achievement description"))
    achievement_date = models.DateField(_("achievement date"))
    organization = models.CharField(_("organizing body"), max_length=200, blank=True)
    position = models.CharField(_("position/rank"), max_length=50, blank=True)
    certificate = models.FileField(
        _("certificate"), upload_to="achievements/certificates/", null=True, blank=True
    )
    prize_money = models.DecimalField(
        _("prize money"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    recognized_by = models.CharField(_("recognized by"), max_length=200, blank=True)
    notes = models.TextField(_("additional notes"), blank=True)

    class Meta:
        verbose_name = _("Achievement")
        verbose_name_plural = _("Achievements")
        ordering = ["-achievement_date", "student"]
        indexes = [
            models.Index(fields=["student", "achievement_type"]),
            models.Index(fields=["achievement_date", "achievement_level"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.title}"


class ParentGuardian(CoreBaseModel, AddressModel, ContactModel):
    """
    Parent and guardian information with relationships to students
    """

    class Relationship(models.TextChoices):
        FATHER = "father", _("Father")
        MOTHER = "mother", _("Mother")
        GUARDIAN = "guardian", _("Guardian")
        GRANDFATHER = "grandfather", _("Grandfather")
        GRANDMOTHER = "grandmother", _("Grandmother")
        UNCLE = "uncle", _("Uncle")
        AUNT = "aunt", _("Aunt")
        OTHER = "other", _("Other")

    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="parent_profile",
        verbose_name=_("user account"),
        null=True,
        blank=True,
    )
    first_name = models.CharField(_("first name"), max_length=50)
    last_name = models.CharField(_("last name"), max_length=50)
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)
    gender = models.CharField(
        _("gender"),
        max_length=10,
        choices=[("male", _("Male")), ("female", _("Female")), ("other", _("Other"))],
    )
    occupation = models.CharField(_("occupation"), max_length=100, blank=True)
    employer = models.CharField(_("employer"), max_length=100, blank=True)
    annual_income = models.DecimalField(
        _("annual income"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    education_level = models.CharField(_("education level"), max_length=100, blank=True)
    is_primary_contact = models.BooleanField(_("is primary contact"), default=False)
    can_pickup_student = models.BooleanField(_("can pickup student"), default=True)
    emergency_contact_priority = models.PositiveIntegerField(
        _("emergency contact priority"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
    )

    class Meta:
        verbose_name = _("Parent/Guardian")
        verbose_name_plural = _("Parents/Guardians")
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["is_primary_contact"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class StudentParentRelationship(CoreBaseModel):
    """
    Relationship between students and their parents/guardians
    """

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="parent_relationships",
        verbose_name=_("student"),
    )
    parent = models.ForeignKey(
        ParentGuardian,
        on_delete=models.CASCADE,
        related_name="student_relationships",
        verbose_name=_("parent/guardian"),
    )
    relationship = models.CharField(
        _("relationship"), max_length=20, choices=ParentGuardian.Relationship.choices
    )
    is_legal_guardian = models.BooleanField(_("is legal guardian"), default=False)
    has_custody = models.BooleanField(_("has custody"), default=True)
    lives_with_student = models.BooleanField(_("lives with student"), default=True)
    can_authorize_medical = models.BooleanField(
        _("can authorize medical treatment"), default=False
    )
    can_access_records = models.BooleanField(
        _("can access student records"), default=True
    )
    notes = models.TextField(_("relationship notes"), blank=True)

    class Meta:
        verbose_name = _("Student-Parent Relationship")
        verbose_name_plural = _("Student-Parent Relationships")
        unique_together = ["student", "parent"]
        ordering = ["student", "parent"]
        indexes = [
            models.Index(fields=["student", "relationship"]),
            models.Index(fields=["parent", "is_legal_guardian"]),
        ]

    def __str__(self):
        return f"{self.parent} - {self.relationship} of {self.student}"


class ClassTransferHistory(CoreBaseModel):
    """
    History of student class transfers
    """

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="transfer_history",
        verbose_name=_("student"),
    )
    from_class = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="transfers_out",
        verbose_name=_("from class"),
    )
    to_class = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="transfers_in",
        verbose_name=_("to class"),
    )
    transfer_date = models.DateField(_("transfer date"))
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="class_transfers",
        verbose_name=_("academic session"),
    )
    reason = models.TextField(_("transfer reason"))
    initiated_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="initiated_transfers",
        verbose_name=_("initiated by"),
    )
    approved_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_transfers",
        verbose_name=_("approved by"),
    )
    notes = models.TextField(_("additional notes"), blank=True)

    class Meta:
        verbose_name = _("Class Transfer History")
        verbose_name_plural = _("Class Transfer History")
        ordering = ["-transfer_date", "student"]
        indexes = [
            models.Index(fields=["student", "transfer_date"]),
            models.Index(fields=["from_class", "to_class"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.from_class} to {self.to_class}"


class AcademicWarning(CoreBaseModel):
    """
    Academic warnings and notices for students
    """

    class WarningType(models.TextChoices):
        ATTENDANCE = "attendance", _("Attendance")
        ACADEMIC_PERFORMANCE = "academic_performance", _("Academic Performance")
        BEHAVIOR = "behavior", _("Behavior")
        FEE_DEFAULT = "fee_default", _("Fee Default")
        OTHER = "other", _("Other")

    class WarningLevel(models.TextChoices):
        INFO = "info", _("Information")
        WARNING = "warning", _("Warning")
        SERIOUS = "serious", _("Serious")
        CRITICAL = "critical", _("Critical")

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="academic_warnings",
        verbose_name=_("student"),
    )
    warning_type = models.CharField(
        _("warning type"), max_length=30, choices=WarningType.choices
    )
    warning_level = models.CharField(
        _("warning level"),
        max_length=20,
        choices=WarningLevel.choices,
        default=WarningLevel.WARNING,
    )
    title = models.CharField(_("warning title"), max_length=200)
    description = models.TextField(_("warning description"))
    issued_date = models.DateField(_("issued date"), auto_now_add=True)
    issued_by = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="issued_warnings",
        verbose_name=_("issued by"),
    )
    due_date = models.DateField(_("resolution due date"), null=True, blank=True)
    is_resolved = models.BooleanField(_("is resolved"), default=False)
    resolution_date = models.DateField(_("resolution date"), null=True, blank=True)
    resolution_notes = models.TextField(_("resolution notes"), blank=True)
    parent_notified = models.BooleanField(_("parent notified"), default=False)
    parent_notification_date = models.DateField(
        _("parent notification date"), null=True, blank=True
    )

    class Meta:
        verbose_name = _("Academic Warning")
        verbose_name_plural = _("Academic Warnings")
        ordering = ["-issued_date", "warning_level"]
        indexes = [
            models.Index(fields=["student", "is_resolved"]),
            models.Index(fields=["warning_type", "warning_level"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.warning_type} - {self.issued_date}"


class Holiday(CoreBaseModel):
    """
    Model for managing holidays and special events.
    """

    name = models.CharField(_("holiday name"), max_length=200)
    date = models.DateField(_("date"))
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="holidays",
        verbose_name=_("academic session"),
    )
    is_recurring = models.BooleanField(_("is recurring"), default=False)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("Holiday")
        verbose_name_plural = _("Holidays")
        ordering = ["date"]
        unique_together = ["date", "academic_session"]

    def __str__(self):
        return f"{self.name} - {self.date}"


class FileAttachment(CoreBaseModel):
    """
    Generic file attachment model for academics app.
    """

    title = models.CharField(_("title"), max_length=200, blank=True)
    file = models.FileField(_("file"), upload_to="attachments/%Y/%m/%d/")
    uploaded_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="file_attachments",
        verbose_name=_("uploaded by"),
    )
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("File Attachment")
        verbose_name_plural = _("File Attachments")
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or self.file.name


class SchoolPolicy(CoreBaseModel):
    """
    Model for managing school-wide policies and schedules.
    """

    class PolicyType(models.TextChoices):
        ACADEMIC = "academic", _("Academic Policy")
        ADMINISTRATIVE = "administrative", _("Administrative Policy")
        DISCIPLINARY = "disciplinary", _("Disciplinary Policy")
        ATTENDANCE = "attendance", _("Attendance Policy")
        FINANCIAL = "financial", _("Financial Policy")
        SAFETY = "safety", _("Safety Policy")
        IT = "it", _("IT Policy")
        OTHER = "other", _("Other Policy")

    policy_name = models.CharField(_("policy name"), max_length=200, unique=True)
    policy_type = models.CharField(
        _("policy type"),
        max_length=20,
        choices=PolicyType.choices,
        default=PolicyType.ACADEMIC,
    )
    description = models.TextField(_("description"))
    policy_content = models.JSONField(
        _("policy content"), default=dict, blank=True, null=True
    )
    effective_date = models.DateField(_("effective date"), default=timezone.now)
    expiry_date = models.DateField(_("expiry date"), null=True, blank=True)
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="school_policies",
        verbose_name=_("academic session"),
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="school_policies",
        verbose_name=_("department"),
    )
    is_active = models.BooleanField(_("is active"), default=True)
    attachments = models.ManyToManyField(
        FileAttachment,
        blank=True,
        related_name="policy_attachments",
        verbose_name=_("attachments"),
    )

    class Meta:
        verbose_name = _("School Policy")
        verbose_name_plural = _("School Policies")
        ordering = ["policy_name", "-effective_date"]
        indexes = [
            models.Index(fields=["policy_type", "is_active"]),
            models.Index(fields=["academic_session", "department"]),
        ]

    def __str__(self):
        return self.policy_name

    def clean(self):
        if (
            self.expiry_date
            and self.effective_date
            and self.expiry_date <= self.effective_date
        ):
            raise ValidationError(_("Expiry date must be after effective date."))

    @property
    def is_current_policy(self):
        """Check if the policy is currently active based on dates."""
        today = timezone.now().date()
        return (
            self.is_active
            and self.effective_date <= today
            and (self.expiry_date is None or self.expiry_date >= today)
        )


# Counseling Models


class CounselingSession(CoreBaseModel):
    """
    Model for tracking counseling sessions between counselors and students.
    """

    class SessionType(models.TextChoices):
        INDIVIDUAL = "individual", _("Individual Counseling")
        GROUP = "group", _("Group Counseling")
        CRISIS = "crisis", _("Crisis Intervention")
        CAREER = "career", _("Career Counseling")
        ACADEMIC = "academic", _("Academic Advising")
        PERSONAL = "personal", _("Personal Counseling")
        FAMILY = "family", _("Family Counseling")

    class SessionStatus(models.TextChoices):
        SCHEDULED = "scheduled", _("Scheduled")
        IN_PROGRESS = "in_progress", _("In Progress")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")
        NO_SHOW = "no_show", _("No Show")

    counselor = models.ForeignKey(
        "academics.Teacher",
        on_delete=models.CASCADE,
        related_name="counseling_sessions",
        verbose_name=_("counselor"),
        limit_choices_to={"user__user_roles__role__role_type": "counselor"},
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="counseling_sessions",
        verbose_name=_("student"),
    )
    session_type = models.CharField(
        _("session type"),
        max_length=20,
        choices=SessionType.choices,
        default=SessionType.INDIVIDUAL,
    )
    session_status = models.CharField(
        _("session status"),
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.SCHEDULED,
    )

    # Scheduling
    scheduled_date = models.DateField(_("scheduled date"))
    scheduled_start_time = models.TimeField(_("scheduled start time"))
    scheduled_end_time = models.TimeField(_("scheduled end time"))
    actual_start_time = models.TimeField(_("actual start time"), null=True, blank=True)
    actual_end_time = models.TimeField(_("actual end time"), null=True, blank=True)

    # Session Details
    session_objectives = models.TextField(_("session objectives"), blank=True)
    session_notes = models.TextField(_("session notes"), blank=True)
    student_concerns = models.TextField(_("student concerns"), blank=True)
    counselor_assessment = models.TextField(_("counselor assessment"), blank=True)
    action_plan = models.TextField(_("action plan"), blank=True)
    follow_up_required = models.BooleanField(_("follow up required"), default=False)
    follow_up_date = models.DateField(_("follow up date"), null=True, blank=True)

    # Referrals and Outcomes
    referral_made = models.BooleanField(_("referral made"), default=False)
    referral_details = models.TextField(_("referral details"), blank=True)
    external_referral = models.BooleanField(_("external referral"), default=False)
    outcome_summary = models.TextField(_("outcome summary"), blank=True)

    # Privacy and Confidentiality
    confidential = models.BooleanField(_("confidential"), default=True)
    emergency_session = models.BooleanField(_("emergency session"), default=False)

    # Academic Context
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="counseling_sessions",
        verbose_name=_("academic session"),
    )

    class Meta:
        verbose_name = _("Counseling Session")
        verbose_name_plural = _("Counseling Sessions")
        ordering = ["-scheduled_date", "-scheduled_start_time"]
        indexes = [
            models.Index(fields=["counselor", "scheduled_date"]),
            models.Index(fields=["student", "scheduled_date"]),
            models.Index(fields=["session_status", "scheduled_date"]),
            models.Index(fields=["session_type", "academic_session"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.session_type} - {self.scheduled_date}"

    def clean(self):
        if self.scheduled_start_time >= self.scheduled_end_time:
            raise ValidationError(_("End time must be after start time."))

        if self.actual_start_time and self.actual_end_time:
            if self.actual_start_time >= self.actual_end_time:
                raise ValidationError(
                    _("Actual end time must be after actual start time.")
                )

    @property
    def duration_minutes(self):
        """Calculate scheduled duration in minutes."""
        if self.scheduled_start_time and self.scheduled_end_time:
            from datetime import datetime

            start_dt = datetime.combine(datetime.today(), self.scheduled_start_time)
            end_dt = datetime.combine(datetime.today(), self.scheduled_end_time)
            return int((end_dt - start_dt).total_seconds() / 60)
        return 0

    @property
    def actual_duration_minutes(self):
        """Calculate actual duration in minutes."""
        if self.actual_start_time and self.actual_end_time:
            from datetime import datetime

            start_dt = datetime.combine(datetime.today(), self.actual_start_time)
            end_dt = datetime.combine(datetime.today(), self.actual_end_time)
            return int((end_dt - start_dt).total_seconds() / 60)
        return 0


class CareerGuidance(CoreBaseModel):
    """
    Model for tracking career guidance and planning activities.
    """

    class GuidanceType(models.TextChoices):
        CAREER_ASSESSMENT = "career_assessment", _("Career Assessment")
        COLLEGE_PREP = "college_prep", _("College Preparation")
        JOB_SEARCH = "job_search", _("Job Search Assistance")
        INTERNSHIP_GUIDANCE = "internship_guidance", _("Internship Guidance")
        RESUME_BUILDING = "resume_building", _("Resume Building")
        INTERVIEW_PREP = "interview_prep", _("Interview Preparation")
        SCHOLARSHIP_INFO = "scholarship_info", _("Scholarship Information")

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="career_guidance",
        verbose_name=_("student"),
    )
    counselor = models.ForeignKey(
        "academics.Teacher",
        on_delete=models.CASCADE,
        related_name="career_guidance_sessions",
        verbose_name=_("counselor"),
        limit_choices_to={"user__user_roles__role__role_type": "counselor"},
    )
    guidance_type = models.CharField(
        _("guidance type"), max_length=30, choices=GuidanceType.choices
    )

    # Session Details
    session_date = models.DateField(_("session date"))
    session_notes = models.TextField(_("session notes"), blank=True)
    goals_discussed = models.TextField(_("goals discussed"), blank=True)
    action_items = models.TextField(_("action items"), blank=True)

    # Career Interests and Plans
    career_interests = models.TextField(_("career interests"), blank=True)
    potential_careers = models.TextField(_("potential careers"), blank=True)
    education_plans = models.TextField(_("education plans"), blank=True)
    timeline = models.TextField(_("timeline"), blank=True)

    # Resources Provided
    resources_provided = models.TextField(_("resources provided"), blank=True)
    referrals_made = models.TextField(_("referrals made"), blank=True)

    # Follow-up
    follow_up_required = models.BooleanField(_("follow up required"), default=False)
    follow_up_date = models.DateField(_("follow up date"), null=True, blank=True)
    progress_notes = models.TextField(_("progress notes"), blank=True)

    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="career_guidance",
        verbose_name=_("academic session"),
    )

    class Meta:
        verbose_name = _("Career Guidance")
        verbose_name_plural = _("Career Guidance")
        ordering = ["-session_date", "student"]
        indexes = [
            models.Index(fields=["student", "session_date"]),
            models.Index(fields=["counselor", "session_date"]),
            models.Index(fields=["guidance_type", "academic_session"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.guidance_type} - {self.session_date}"


class CounselingReferral(CoreBaseModel):
    """
    Model for tracking referrals made by counselors.
    """

    class ReferralType(models.TextChoices):
        MENTAL_HEALTH = "mental_health", _("Mental Health Services")
        MEDICAL = "medical", _("Medical Services")
        SPECIAL_EDUCATION = "special_education", _("Special Education Services")
        SOCIAL_SERVICES = "social_services", _("Social Services")
        LEGAL_AID = "legal_aid", _("Legal Aid")
        CAREER_SERVICES = "career_services", _("Career Services")
        SUBSTANCE_ABUSE = "substance_abuse", _("Substance Abuse Treatment")
        OTHER = "other", _("Other")

    class ReferralStatus(models.TextChoices):
        INITIATED = "initiated", _("Initiated")
        IN_PROGRESS = "in_progress", _("In Progress")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")
        FOLLOW_UP_NEEDED = "follow_up_needed", _("Follow-up Needed")

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="counseling_referrals",
        verbose_name=_("student"),
    )
    counselor = models.ForeignKey(
        "academics.Teacher",
        on_delete=models.CASCADE,
        related_name="counseling_referrals_made",
        verbose_name=_("counselor"),
        limit_choices_to={"user__user_roles__role__role_type": "counselor"},
    )
    referral_type = models.CharField(
        _("referral type"), max_length=30, choices=ReferralType.choices
    )
    referral_status = models.CharField(
        _("referral status"),
        max_length=20,
        choices=ReferralStatus.choices,
        default=ReferralStatus.INITIATED,
    )

    # Referral Details
    referral_date = models.DateField(_("referral date"), auto_now_add=True)
    reason_for_referral = models.TextField(_("reason for referral"))
    urgency_level = models.CharField(
        _("urgency level"),
        max_length=10,
        choices=[
            ("low", _("Low")),
            ("medium", _("Medium")),
            ("high", _("High")),
            ("critical", _("Critical")),
        ],
        default="medium",
    )

    # External Service Details
    service_provider = models.CharField(
        _("service provider"), max_length=200, blank=True
    )
    contact_person = models.CharField(_("contact person"), max_length=100, blank=True)
    contact_phone = models.CharField(_("contact phone"), max_length=20, blank=True)
    contact_email = models.EmailField(_("contact email"), blank=True)
    service_address = models.TextField(_("service address"), blank=True)

    # Internal Tracking
    internal_notes = models.TextField(_("internal notes"), blank=True)
    follow_up_date = models.DateField(_("follow up date"), null=True, blank=True)
    follow_up_notes = models.TextField(_("follow up notes"), blank=True)
    outcome = models.TextField(_("outcome"), blank=True)

    # Parent Communication
    parent_notified = models.BooleanField(_("parent notified"), default=False)
    parent_consent_obtained = models.BooleanField(
        _("parent consent obtained"), default=False
    )

    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="counseling_referrals",
        verbose_name=_("academic session"),
    )

    class Meta:
        verbose_name = _("Counseling Referral")
        verbose_name_plural = _("Counseling Referrals")
        ordering = ["-referral_date", "student"]
        indexes = [
            models.Index(fields=["student", "referral_date"]),
            models.Index(fields=["counselor", "referral_status"]),
            models.Index(fields=["referral_type", "urgency_level"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.referral_type} - {self.referral_date}"


# Academic Planning Committee Models


class AcademicPlanningCommittee(CoreBaseModel):
    """
    Model for academic planning committees.
    """

    class CommitteeType(models.TextChoices):
        CURRICULUM = "curriculum", _("Curriculum Committee")
        ASSESSMENT = "assessment", _("Assessment Committee")
        POLICY = "policy", _("Academic Policy Committee")
        BUDGET = "budget", _("Academic Budget Committee")
        STRATEGIC = "strategic", _("Strategic Planning Committee")
        DEPARTMENT_REVIEW = "department_review", _("Department Review Committee")

    committee_name = models.CharField(_("committee name"), max_length=200)
    committee_type = models.CharField(
        _("committee type"),
        max_length=20,
        choices=CommitteeType.choices,
        default=CommitteeType.CURRICULUM,
    )
    description = models.TextField(_("description"), blank=True)

    # Committee Leadership
    chairperson = models.ForeignKey(
        "academics.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chaired_committees",
        verbose_name=_("chairperson"),
    )
    secretary = models.ForeignKey(
        "academics.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secretary_committees",
        verbose_name=_("secretary"),
    )

    # Committee Members
    members = models.ManyToManyField(
        "academics.Teacher",
        related_name="committee_memberships",
        verbose_name=_("committee members"),
        blank=True,
    )

    # Department/Subject Focus (optional)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="committees",
        verbose_name=_("department"),
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="committees",
        verbose_name=_("subject"),
    )

    # Committee Details
    formation_date = models.DateField(_("formation date"), auto_now_add=True)
    term_start_date = models.DateField(_("term start date"))
    term_end_date = models.DateField(_("term end date"))
    meeting_frequency = models.CharField(
        _("meeting frequency"),
        max_length=50,
        choices=[
            ("weekly", _("Weekly")),
            ("biweekly", _("Bi-weekly")),
            ("monthly", _("Monthly")),
            ("quarterly", _("Quarterly")),
            ("as_needed", _("As Needed")),
        ],
        default="monthly",
    )

    # Status and Activity
    is_active = models.BooleanField(_("is active"), default=True)
    last_meeting_date = models.DateField(_("last meeting date"), null=True, blank=True)
    next_meeting_date = models.DateField(_("next meeting date"), null=True, blank=True)

    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="academic_committees",
        verbose_name=_("academic session"),
    )

    class Meta:
        verbose_name = _("Academic Planning Committee")
        verbose_name_plural = _("Academic Planning Committees")
        ordering = ["committee_name", "-formation_date"]
        indexes = [
            models.Index(fields=["committee_type", "is_active"]),
            models.Index(fields=["department", "academic_session"]),
            models.Index(fields=["term_start_date", "term_end_date"]),
        ]

    def __str__(self):
        return f"{self.committee_name} ({self.get_committee_type_display()})"

    def clean(self):
        if self.term_end_date <= self.term_start_date:
            raise ValidationError(_("Term end date must be after term start date."))

    @property
    def member_count(self):
        """Get total number of committee members."""
        return (
            self.members.count()
            + (1 if self.chairperson else 0)
            + (1 if self.secretary else 0)
        )

    @property
    def is_term_active(self):
        """Check if committee term is currently active."""
        from django.utils import timezone

        today = timezone.now().date()
        return self.term_start_date <= today <= self.term_end_date


class CommitteeMeeting(CoreBaseModel):
    """
    Model for tracking committee meetings and their outcomes.
    """

    class MeetingType(models.TextChoices):
        REGULAR = "regular", _("Regular Meeting")
        SPECIAL = "special", _("Special Meeting")
        EMERGENCY = "emergency", _("Emergency Meeting")

    class MeetingStatus(models.TextChoices):
        SCHEDULED = "scheduled", _("Scheduled")
        IN_PROGRESS = "in_progress", _("In Progress")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")
        POSTPONED = "postponed", _("Postponed")

    committee = models.ForeignKey(
        AcademicPlanningCommittee,
        on_delete=models.CASCADE,
        related_name="meetings",
        verbose_name=_("committee"),
    )
    meeting_type = models.CharField(
        _("meeting type"),
        max_length=20,
        choices=MeetingType.choices,
        default=MeetingType.REGULAR,
    )
    meeting_status = models.CharField(
        _("meeting status"),
        max_length=20,
        choices=MeetingStatus.choices,
        default=MeetingStatus.SCHEDULED,
    )

    # Meeting Details
    meeting_date = models.DateField(_("meeting date"))
    start_time = models.TimeField(_("start time"))
    end_time = models.TimeField(_("end time"), null=True, blank=True)
    location = models.CharField(_("location"), max_length=200, blank=True)
    agenda = models.TextField(_("agenda"), blank=True)
    meeting_objectives = models.TextField(_("meeting objectives"), blank=True)

    # Attendance
    attendees = models.ManyToManyField(
        "academics.Teacher",
        related_name="committee_attendance",
        verbose_name=_("attendees"),
        blank=True,
    )
    absentees = models.ManyToManyField(
        "academics.Teacher",
        related_name="committee_absences",
        verbose_name=_("absentees"),
        blank=True,
    )

    # Meeting Content
    minutes = models.TextField(_("meeting minutes"), blank=True)
    decisions_made = models.TextField(_("decisions made"), blank=True)
    action_items = models.TextField(_("action items"), blank=True)
    next_steps = models.TextField(_("next steps"), blank=True)

    # Follow-up
    follow_up_required = models.BooleanField(_("follow up required"), default=False)
    follow_up_date = models.DateField(_("follow up date"), null=True, blank=True)
    follow_up_notes = models.TextField(_("follow up notes"), blank=True)

    # Additional Info
    special_notes = models.TextField(_("special notes"), blank=True)
    attachments = models.ManyToManyField(
        FileAttachment,
        blank=True,
        related_name="committee_meetings",
        verbose_name=_("attachments"),
    )

    class Meta:
        verbose_name = _("Committee Meeting")
        verbose_name_plural = _("Committee Meetings")
        ordering = ["-meeting_date", "-start_time"]
        indexes = [
            models.Index(fields=["committee", "meeting_date"]),
            models.Index(fields=["meeting_status", "meeting_date"]),
            models.Index(fields=["meeting_type", "committee"]),
        ]

    def __str__(self):
        return f"{self.committee} - {self.meeting_date}"

    def clean(self):
        if self.end_time and self.start_time >= self.end_time:
            raise ValidationError(_("End time must be after start time."))

    @property
    def duration_minutes(self):
        """Calculate meeting duration in minutes."""
        if self.start_time and self.end_time:
            from datetime import datetime

            start_dt = datetime.combine(datetime.today(), self.start_time)
            end_dt = datetime.combine(datetime.today(), self.end_time)
            return int((end_dt - start_dt).total_seconds() / 60)
        return 0

    @property
    def attendance_rate(self):
        """Calculate attendance rate."""
        total_members = self.committee.member_count
        if total_members > 0:
            return (self.attendees.count() / total_members) * 100
        return 0


class DepartmentBudget(CoreBaseModel):
    """
    Model for managing department-specific budgets.
    """

    class BudgetCategory(models.TextChoices):
        TEACHING_MATERIALS = "teaching_materials", _("Teaching Materials")
        EQUIPMENT = "equipment", _("Equipment")
        PROFESSIONAL_DEVELOPMENT = "professional_development", _(
            "Professional Development"
        )
        STUDENT_ACTIVITIES = "student_activities", _("Student Activities")
        MAINTENANCE = "maintenance", _("Maintenance")
        TRAVEL = "travel", _("Travel")
        OTHER = "other", _("Other")

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="budgets",
        verbose_name=_("department"),
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="department_budgets",
        verbose_name=_("academic session"),
    )

    # Budget Details
    budget_category = models.CharField(
        _("budget category"), max_length=30, choices=BudgetCategory.choices
    )
    allocated_amount = models.DecimalField(
        _("allocated amount"),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    spent_amount = models.DecimalField(
        _("spent amount"),
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    description = models.TextField(_("description"), blank=True)

    # Approval and Tracking
    requested_by = models.ForeignKey(
        "academics.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        related_name="budget_requests",
        verbose_name=_("requested by"),
    )
    approved_by = models.ForeignKey(
        "academics.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="budget_approvals",
        verbose_name=_("approved by"),
        limit_choices_to={
            "user__user_roles__role__role_type__in": ["principal", "department_head"]
        },
    )
    approval_date = models.DateField(_("approval date"), null=True, blank=True)

    # Status
    is_approved = models.BooleanField(_("is approved"), default=False)
    is_active = models.BooleanField(_("is active"), default=True)

    class Meta:
        verbose_name = _("Department Budget")
        verbose_name_plural = _("Department Budgets")
        ordering = ["department", "budget_category", "-created_at"]
        indexes = [
            models.Index(fields=["department", "academic_session"]),
            models.Index(fields=["budget_category", "is_approved"]),
            models.Index(fields=["is_active", "academic_session"]),
        ]

    def __str__(self):
        return f"{self.department} - {self.budget_category} - {self.academic_session}"

    def clean(self):
        if self.spent_amount > self.allocated_amount:
            raise ValidationError(_("Spent amount cannot exceed allocated amount."))

    @property
    def remaining_amount(self):
        """Calculate remaining budget amount."""
        return self.allocated_amount - self.spent_amount

    @property
    def utilization_percentage(self):
        """Calculate budget utilization percentage."""
        if self.allocated_amount > 0:
            return (self.spent_amount / self.allocated_amount) * 100
        return 0

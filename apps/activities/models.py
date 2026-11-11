# apps/activities/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import CoreBaseModel


class ActivityCategory(CoreBaseModel):
    """
    Categories for extracurricular activities (Sports, Arts, Clubs, etc.)
    """
    class CategoryType(models.TextChoices):
        SPORTS = 'sports', _('Sports')
        ARTS = 'arts', _('Arts')
        CLUBS = 'clubs', _('Clubs')
        COMPETITIONS = 'competitions', _('Competitions')
        ACADEMIC_CLUBS = 'academic_clubs', _('Academic Clubs')
        CULTURAL = 'cultural', _('Cultural')
        COMMUNITY_SERVICE = 'community_service', _('Community Service')
        OTHER = 'other', _('Other')

    name = models.CharField(_('category name'), max_length=100, unique=True)
    category_type = models.CharField(
        _('category type'),
        max_length=20,
        choices=CategoryType.choices,
        default=CategoryType.OTHER
    )
    description = models.TextField(_('description'), blank=True)
    icon = models.CharField(_('icon'), max_length=50, blank=True, help_text=_('FontAwesome icon class'))
    color_code = models.CharField(_('color code'), max_length=7, default='#3498db')
    is_active = models.BooleanField(_('is active'), default=True)

    class Meta:
        verbose_name = _('Activity Category')
        verbose_name_plural = _('Activity Categories')
        ordering = ['name']

    def __str__(self):
        return self.name


class Activity(CoreBaseModel):
    """
    Main model for extracurricular activities
    """
    class ActivityType(models.TextChoices):
        INDIVIDUAL = 'individual', _('Individual')
        TEAM = 'team', _('Team')
        GROUP = 'group', _('Group')

    class Frequency(models.TextChoices):
        ONE_TIME = 'one_time', _('One Time')
        WEEKLY = 'weekly', _('Weekly')
        BIWEEKLY = 'biweekly', _('Bi-weekly')
        MONTHLY = 'monthly', _('Monthly')
        SEASONAL = 'seasonal', _('Seasonal')

    class Status(models.TextChoices):
        PLANNING = 'planning', _('Planning')
        ACTIVE = 'active', _('Active')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')

    # Basic Information
    title = models.CharField(_('activity title'), max_length=200)
    description = models.TextField(_('description'))
    category = models.ForeignKey(
        ActivityCategory,
        on_delete=models.CASCADE,
        related_name='activities',
        verbose_name=_('category')
    )

    # Activity Details
    activity_type = models.CharField(
        _('activity type'),
        max_length=20,
        choices=ActivityType.choices,
        default=ActivityType.INDIVIDUAL
    )
    frequency = models.CharField(
        _('frequency'),
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.ONE_TIME
    )
    max_participants = models.PositiveIntegerField(_('maximum participants'), null=True, blank=True)
    min_participants = models.PositiveIntegerField(_('minimum participants'), default=1)

    # Scheduling
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'), null=True, blank=True)
    start_time = models.TimeField(_('start time'), null=True, blank=True)
    end_time = models.TimeField(_('end time'), null=True, blank=True)
    days_of_week = models.CharField(_('days of week'), max_length=100, blank=True,
                                   help_text=_('Comma-separated days (monday,tuesday,etc.)'))

    # Location & Resources
    venue = models.CharField(_('venue'), max_length=200, blank=True)
    room_number = models.CharField(_('room number'), max_length=20, blank=True)
    equipment_needed = models.TextField(_('equipment needed'), blank=True)

    # Financial
    fee_amount = models.DecimalField(_('fee amount'), max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(_('currency'), max_length=3, default='USD')

    # Status & Management
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNING
    )
    academic_session = models.ForeignKey(
        'academics.AcademicSession',
        on_delete=models.CASCADE,
        related_name='activities',
        verbose_name=_('academic session')
    )

    # Staff Assignments
    coordinator = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coordinated_activities',
        verbose_name=_('coordinator')
    )

    # Metadata
    prerequisites = models.TextField(_('prerequisites'), blank=True)
    objectives = models.TextField(_('learning objectives'), blank=True)
    contact_info = models.TextField(_('contact information'), blank=True)
    registration_deadline = models.DateField(_('registration deadline'), null=True, blank=True)

    # Media
    image = models.ImageField(_('activity image'), upload_to='activities/images/', null=True, blank=True)
    brochure = models.FileField(_('brochure'), upload_to='activities/brochures/', null=True, blank=True)

    class Meta:
        verbose_name = _('Activity')
        verbose_name_plural = _('Activities')
        ordering = ['-start_date', 'title']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['academic_session', 'status']),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError(_('End date must be after start date.'))

        if self.registration_deadline and self.registration_deadline > self.start_date:
            raise ValidationError(_('Registration deadline must be before start date.'))

        if self.min_participants and self.max_participants and self.min_participants > self.max_participants:
            raise ValidationError(_('Minimum participants cannot exceed maximum participants.'))

    @property
    def current_participants(self):
        """Return current number of enrolled participants."""
        return self.enrollments.filter(status='active').count()

    @property
    def available_spots(self):
        """Return number of available spots."""
        if not self.max_participants:
            return None
        return max(0, self.max_participants - self.current_participants)

    @property
    def is_full(self):
        """Check if activity is at capacity."""
        return self.max_participants and self.current_participants >= self.max_participants

    @property
    def is_registration_open(self):
        """Check if registration is still open."""
        today = timezone.now().date()
        if self.registration_deadline:
            return today <= self.registration_deadline
        return today <= self.start_date

    @property
    def duration_hours(self):
        """Calculate activity duration in hours."""
        if self.start_time and self.end_time:
            from datetime import datetime
            start_dt = datetime.combine(datetime.today(), self.start_time)
            end_dt = datetime.combine(datetime.today(), self.end_time)
            duration = end_dt - start_dt
            return duration.total_seconds() / 3600
        return None


class ActivityEnrollment(CoreBaseModel):
    """
    Student enrollment in activities
    """
    class EnrollmentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        ACTIVE = 'active', _('Active')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
        WAITLISTED = 'waitlisted', _('Waitlisted')

    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='activity_enrollments',
        verbose_name=_('student')
    )
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name=_('activity')
    )
    enrollment_date = models.DateField(_('enrollment date'), auto_now_add=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.PENDING
    )

    # Additional information
    special_requirements = models.TextField(_('special requirements'), blank=True)
    emergency_contact = models.CharField(_('emergency contact'), max_length=100, blank=True)
    medical_conditions = models.TextField(_('medical conditions'), blank=True)

    # Payment
    payment_status = models.BooleanField(_('payment completed'), default=False)
    payment_date = models.DateField(_('payment date'), null=True, blank=True)
    transaction_id = models.CharField(_('transaction ID'), max_length=100, blank=True)

    # Attendance tracking
    attendance_count = models.PositiveIntegerField(_('attendance count'), default=0)
    last_attendance = models.DateField(_('last attendance'), null=True, blank=True)

    # Performance/feedback
    performance_notes = models.TextField(_('performance notes'), blank=True)
    grade = models.CharField(_('grade'), max_length=5, blank=True)
    certificate_issued = models.BooleanField(_('certificate issued'), default=False)

    class Meta:
        verbose_name = _('Activity Enrollment')
        verbose_name_plural = _('Activity Enrollments')
        unique_together = ['student', 'activity']
        ordering = ['-enrollment_date']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['activity', 'status']),
            models.Index(fields=['enrollment_date', 'status']),
        ]

    def __str__(self):
        return f"{self.student} - {self.activity}"

    @property
    def attendance_percentage(self):
        """Calculate attendance percentage."""
        if not hasattr(self.activity, 'total_sessions'):
            return None
        if self.activity.total_sessions == 0:
            return 0
        return (self.attendance_count / self.activity.total_sessions) * 100


class ActivityStaffAssignment(CoreBaseModel):
    """
    Assignment of staff to activities (coaches, advisors, etc.)
    """
    class RoleType(models.TextChoices):
        COORDINATOR = 'coordinator', _('Coordinator')
        COACH = 'coach', _('Coach')
        ASSISTANT_COACH = 'assistant_coach', _('Assistant Coach')
        ADVISOR = 'advisor', _('Advisor')
        VOLUNTEER = 'volunteer', _('Volunteer')

    staff_member = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='activity_assignments',
        verbose_name=_('staff member')
    )
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='staff_assignments',
        verbose_name=_('activity')
    )
    role = models.CharField(
        _('role'),
        max_length=20,
        choices=RoleType.choices,
        default=RoleType.COACH
    )

    # Assignment details
    assigned_date = models.DateField(_('assigned date'), auto_now_add=True)
    is_primary = models.BooleanField(_('is primary'), default=False)
    responsibilities = models.TextField(_('responsibilities'), blank=True)

    # Compensation (if applicable)
    hourly_rate = models.DecimalField(_('hourly rate'), max_digits=8, decimal_places=2, null=True, blank=True)
    hours_per_week = models.DecimalField(_('hours per week'), max_digits=4, decimal_places=1, null=True, blank=True)

    class Meta:
        verbose_name = _('Activity Staff Assignment')
        verbose_name_plural = _('Activity Staff Assignments')
        unique_together = ['staff_member', 'activity', 'role']
        ordering = ['activity', 'role']
        indexes = [
            models.Index(fields=['staff_member', 'activity']),
            models.Index(fields=['activity', 'role']),
        ]

    def __str__(self):
        return f"{self.staff_member.get_full_name()} - {self.activity.title} ({self.get_role_display()})"


class SportsTeam(CoreBaseModel):
    """
    Sports teams within activities
    """
    class TeamLevel(models.TextChoices):
        BEGINNER = 'beginner', _('Beginner')
        INTERMEDIATE = 'intermediate', _('Intermediate')
        ADVANCED = 'advanced', _('Advanced')
        COMPETITIVE = 'competitive', _('Competitive')

    activity = models.OneToOneField(
        Activity,
        on_delete=models.CASCADE,
        related_name='sports_team',
        verbose_name=_('activity')
    )
    team_name = models.CharField(_('team name'), max_length=100)
    team_level = models.CharField(
        _('team level'),
        max_length=20,
        choices=TeamLevel.choices,
        default=TeamLevel.BEGINNER
    )

    # Team details
    max_players = models.PositiveIntegerField(_('maximum players'), default=15)
    min_players = models.PositiveIntegerField(_('minimum players'), default=8)

    # Captain/Vice Captain
    captain = models.ForeignKey(
        'academics.Student',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='captained_teams',
        verbose_name=_('captain')
    )
    vice_captain = models.ForeignKey(
        'academics.Student',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vice_captained_teams',
        verbose_name=_('vice captain')
    )

    # Performance tracking
    wins = models.PositiveIntegerField(_('wins'), default=0)
    losses = models.PositiveIntegerField(_('losses'), default=0)
    draws = models.PositiveIntegerField(_('draws'), default=0)
    points = models.PositiveIntegerField(_('points'), default=0)

    class Meta:
        verbose_name = _('Sports Team')
        verbose_name_plural = _('Sports Teams')
        ordering = ['team_name']

    def __str__(self):
        return f"{self.team_name} - {self.activity.title}"

    @property
    def current_players(self):
        """Return current number of players."""
        return self.activity.enrollments.filter(status='active').count()

    @property
    def matches_played(self):
        """Return total matches played."""
        return self.wins + self.losses + self.draws


class Club(CoreBaseModel):
    """
    Clubs within activities
    """
    class ClubType(models.TextChoices):
        ACADEMIC = 'academic', _('Academic')
        CULTURAL = 'cultural', _('Cultural')
        SERVICE = 'service', _('Service')
        SPECIAL_INTEREST = 'special_interest', _('Special Interest')
        OTHER = 'other', _('Other')

    activity = models.OneToOneField(
        Activity,
        on_delete=models.CASCADE,
        related_name='club',
        verbose_name=_('activity')
    )
    club_type = models.CharField(
        _('club type'),
        max_length=20,
        choices=ClubType.choices,
        default=ClubType.OTHER
    )

    # Club details
    mission_statement = models.TextField(_('mission statement'), blank=True)
    meeting_schedule = models.TextField(_('meeting schedule'), blank=True)

    # Leadership
    president = models.ForeignKey(
        'academics.Student',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='presided_clubs',
        verbose_name=_('president')
    )
    vice_president = models.ForeignKey(
        'academics.Student',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vice_presided_clubs',
        verbose_name=_('vice president')
    )
    secretary = models.ForeignKey(
        'academics.Student',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='secretary_clubs',
        verbose_name=_('secretary')
    )

    # Budget and resources
    budget_allocated = models.DecimalField(_('budget allocated'), max_digits=10, decimal_places=2, default=0.00)
    resources_needed = models.TextField(_('resources needed'), blank=True)

    class Meta:
        verbose_name = _('Club')
        verbose_name_plural = _('Clubs')
        ordering = ['activity__title']

    def __str__(self):
        return f"{self.activity.title} Club"


class Competition(CoreBaseModel):
    """
    Competitions and tournaments
    """
    class CompetitionType(models.TextChoices):
        TOURNAMENT = 'tournament', _('Tournament')
        LEAGUE = 'league', _('League')
        CHAMPIONSHIP = 'championship', _('Championship')
        FRIENDLY = 'friendly', _('Friendly Match')
        OTHER = 'other', _('Other')

    class CompetitionLevel(models.TextChoices):
        SCHOOL = 'school', _('School Level')
        DISTRICT = 'district', _('District Level')
        STATE = 'state', _('State Level')
        NATIONAL = 'national', _('National Level')
        INTERNATIONAL = 'international', _('International Level')

    title = models.CharField(_('competition title'), max_length=200)
    description = models.TextField(_('description'))
    competition_type = models.CharField(
        _('competition type'),
        max_length=20,
        choices=CompetitionType.choices,
        default=CompetitionType.TOURNAMENT
    )
    level = models.CharField(
        _('competition level'),
        max_length=20,
        choices=CompetitionLevel.choices,
        default=CompetitionLevel.SCHOOL
    )

    # Related activity
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='competitions',
        verbose_name=_('related activity')
    )

    # Scheduling
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'), null=True, blank=True)
    registration_deadline = models.DateField(_('registration deadline'), null=True, blank=True)

    # Participants
    max_teams = models.PositiveIntegerField(_('maximum teams'), null=True, blank=True)
    max_individuals = models.PositiveIntegerField(_('maximum individuals'), null=True, blank=True)

    # Rules and format
    rules = models.TextField(_('rules and regulations'))
    format_description = models.TextField(_('format description'), blank=True)
    scoring_system = models.TextField(_('scoring system'), blank=True)

    # Prizes
    first_prize = models.CharField(_('first prize'), max_length=200, blank=True)
    second_prize = models.CharField(_('second prize'), max_length=200, blank=True)
    third_prize = models.CharField(_('third prize'), max_length=200, blank=True)

    # Venue and logistics
    venue = models.CharField(_('venue'), max_length=200, blank=True)
    contact_person = models.CharField(_('contact person'), max_length=100, blank=True)
    contact_email = models.EmailField(_('contact email'), blank=True)

    # Status
    is_active = models.BooleanField(_('is active'), default=True)

    class Meta:
        verbose_name = _('Competition')
        verbose_name_plural = _('Competitions')
        ordering = ['-start_date', 'title']
        indexes = [
            models.Index(fields=['activity', 'start_date']),
            models.Index(fields=['competition_type', 'level']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_level_display()})"


class Equipment(CoreBaseModel):
    """
    Equipment and resources for activities
    """
    class EquipmentType(models.TextChoices):
        SPORTS = 'sports', _('Sports Equipment')
        ARTS = 'arts', _('Arts Supplies')
        ELECTRONICS = 'electronics', _('Electronics')
        BOOKS = 'books', _('Books/Materials')
        UNIFORMS = 'uniforms', _('Uniforms')
        OTHER = 'other', _('Other')

    class Condition(models.TextChoices):
        EXCELLENT = 'excellent', _('Excellent')
        GOOD = 'good', _('Good')
        FAIR = 'fair', _('Fair')
        POOR = 'poor', _('Poor')
        DAMAGED = 'damaged', _('Damaged')

    name = models.CharField(_('equipment name'), max_length=200)
    equipment_type = models.CharField(
        _('equipment type'),
        max_length=20,
        choices=EquipmentType.choices,
        default=EquipmentType.OTHER
    )
    description = models.TextField(_('description'), blank=True)

    # Inventory
    quantity_total = models.PositiveIntegerField(_('total quantity'), default=1)
    quantity_available = models.PositiveIntegerField(_('available quantity'), default=1)
    condition = models.CharField(
        _('condition'),
        max_length=20,
        choices=Condition.choices,
        default=Condition.GOOD
    )

    # Financial
    purchase_price = models.DecimalField(_('purchase price'), max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_date = models.DateField(_('purchase date'), null=True, blank=True)
    supplier = models.CharField(_('supplier'), max_length=100, blank=True)

    # Maintenance
    last_maintenance = models.DateField(_('last maintenance'), null=True, blank=True)
    next_maintenance = models.DateField(_('next maintenance'), null=True, blank=True)
    maintenance_notes = models.TextField(_('maintenance notes'), blank=True)

    # Assignment
    assigned_to_activity = models.ForeignKey(
        Activity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment',
        verbose_name=_('assigned to activity')
    )

    # Storage
    storage_location = models.CharField(_('storage location'), max_length=100, blank=True)

    class Meta:
        verbose_name = _('Equipment')
        verbose_name_plural = _('Equipment')
        ordering = ['equipment_type', 'name']
        indexes = [
            models.Index(fields=['equipment_type', 'condition']),
            models.Index(fields=['assigned_to_activity']),
        ]

    def __str__(self):
        return f"{self.name} ({self.quantity_available}/{self.quantity_total})"

    @property
    def is_available(self):
        """Check if equipment is available."""
        return self.quantity_available > 0

    @property
    def utilization_rate(self):
        """Calculate utilization rate."""
        if self.quantity_total == 0:
            return 0
        used = self.quantity_total - self.quantity_available
        return (used / self.quantity_total) * 100


class ActivityBudget(CoreBaseModel):
    """
    Budget tracking for activities
    """
    class BudgetType(models.TextChoices):
        REVENUE = 'revenue', _('Revenue')
        EXPENSE = 'expense', _('Expense')

    class Category(models.TextChoices):
        EQUIPMENT = 'equipment', _('Equipment')
        VENUE = 'venue', _('Venue Rental')
        TRANSPORT = 'transport', _('Transportation')
        MATERIALS = 'materials', _('Materials/Supplies')
        STAFF = 'staff', _('Staff Compensation')
        MARKETING = 'marketing', _('Marketing/Promotion')
        FEES = 'fees', _('Registration Fees')
        SPONSORSHIP = 'sponsorship', _('Sponsorship')
        OTHER = 'other', _('Other')

    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='budget_items',
        verbose_name=_('activity')
    )
    budget_type = models.CharField(
        _('budget type'),
        max_length=20,
        choices=BudgetType.choices
    )
    category = models.CharField(
        _('category'),
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER
    )

    # Financial details
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    description = models.TextField(_('description'), blank=True)

    # Dates
    planned_date = models.DateField(_('planned date'), null=True, blank=True)
    actual_date = models.DateField(_('actual date'), null=True, blank=True)

    # Approval and tracking
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_budget_items',
        verbose_name=_('approved by')
    )
    approval_date = models.DateField(_('approval date'), null=True, blank=True)

    # Supporting documents
    receipt = models.FileField(_('receipt'), upload_to='activities/budgets/', null=True, blank=True)

    class Meta:
        verbose_name = _('Activity Budget')
        verbose_name_plural = _('Activity Budgets')
        ordering = ['activity', '-planned_date']
        indexes = [
            models.Index(fields=['activity', 'budget_type']),
            models.Index(fields=['category', 'budget_type']),
        ]

    def __str__(self):
        return f"{self.activity.title} - {self.get_budget_type_display()} - {self.amount}"


class ActivityAttendance(CoreBaseModel):
    """
    Attendance tracking for activity sessions
    """
    enrollment = models.ForeignKey(
        ActivityEnrollment,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        verbose_name=_('enrollment')
    )
    session_date = models.DateField(_('session date'))
    is_present = models.BooleanField(_('is present'), default=False)
    arrival_time = models.TimeField(_('arrival time'), null=True, blank=True)
    departure_time = models.TimeField(_('departure time'), null=True, blank=True)
    notes = models.TextField(_('notes'), blank=True)

    # Performance tracking
    participation_rating = models.PositiveIntegerField(
        _('participation rating'),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Rate participation from 1-5')
    )

    class Meta:
        verbose_name = _('Activity Attendance')
        verbose_name_plural = _('Activity Attendance')
        unique_together = ['enrollment', 'session_date']
        ordering = ['-session_date']
        indexes = [
            models.Index(fields=['enrollment', 'session_date']),
            models.Index(fields=['session_date', 'is_present']),
        ]

    def __str__(self):
        return f"{self.enrollment.student} - {self.enrollment.activity.title} - {self.session_date}"


class ActivityAchievement(CoreBaseModel):
    """
    Achievements and awards for activity participants
    """
    class AchievementType(models.TextChoices):
        PARTICIPATION = 'participation', _('Participation')
        PERFORMANCE = 'performance', _('Performance')
        LEADERSHIP = 'leadership', _('Leadership')
        TEAM_PLAYER = 'team_player', _('Team Player')
        IMPROVEMENT = 'improvement', _('Improvement')
        OTHER = 'other', _('Other')

    enrollment = models.ForeignKey(
        ActivityEnrollment,
        on_delete=models.CASCADE,
        related_name='achievements',
        verbose_name=_('enrollment')
    )
    achievement_type = models.CharField(
        _('achievement type'),
        max_length=20,
        choices=AchievementType.choices,
        default=AchievementType.PARTICIPATION
    )
    title = models.CharField(_('achievement title'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    achievement_date = models.DateField(_('achievement date'))

    # Recognition
    awarded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='awarded_achievements',
        verbose_name=_('awarded by')
    )
    certificate_issued = models.BooleanField(_('certificate issued'), default=False)
    certificate_number = models.CharField(_('certificate number'), max_length=50, blank=True)

    # Media
    photo = models.ImageField(_('achievement photo'), upload_to='activities/achievements/', null=True, blank=True)

    class Meta:
        verbose_name = _('Activity Achievement')
        verbose_name_plural = _('Activity Achievements')
        ordering = ['-achievement_date']
        indexes = [
            models.Index(fields=['enrollment', 'achievement_date']),
            models.Index(fields=['achievement_type', 'achievement_date']),
        ]

    def __str__(self):
        return f"{self.enrollment.student} - {self.title}"

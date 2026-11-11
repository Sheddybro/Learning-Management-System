import os
import django
from django.contrib.auth import get_user_model as django_get_user_model


def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        django.setup()
    except Exception:
        pass


def get_user_model():
    return django_get_user_model()


def create_superadmin(
    username="superadmin", email="admin@example.com", password="admin"
):
    User = get_user_model()
    # Project uses email as USERNAME_FIELD; create/find by email
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": username,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    if created:
        user.set_password(password)
        user.save()
    return user


def ensure_site_entities():
    # This function should be extended to populate models used by the superadmin
    # For now it creates a superuser; apps can add more population steps in their scripts
    from django.contrib.sites.models import Site

    site, _ = Site.objects.get_or_create(
        pk=1, defaults={"domain": "example.com", "name": "Example"}
    )
    return site


def create_institution(name, code, defaults=None):
    """Create or get an Institution by name/code and return it."""
    setup_django()
    from django.apps import apps

    Institution = apps.get_model("core", "Institution")
    params = {"name": name, "code": code}
    if defaults:
        params.update(defaults)

    # Prefer exact code match
    try:
        return Institution.objects.get(code=code)
    except Institution.DoesNotExist:
        pass

    # If name exists, return that institution to avoid unique constraint errors
    try:
        return Institution.objects.get(name=name)
    except Institution.DoesNotExist:
        pass

    # Otherwise create a new institution
    inst = Institution.objects.create(**params)
    return inst


def populate_superadmin_entities_for_institution(institution):
    """Create common roles, sequence generators and basic configs for an institution."""
    from django.apps import apps

    try:
        Role = apps.get_model("users", "Role")
    except Exception:
        Role = None

    try:
        SequenceGenerator = apps.get_model("core", "SequenceGenerator")
    except Exception:
        SequenceGenerator = None

    created = {}

    # Create some system roles
    if Role:
        system_roles = [
            ("Super Administrator", "super_admin", 100),
            ("School Administrator", "school_admin", 90),
            ("Teacher", "teacher", 10),
            ("Student", "student", 1),
        ]
        for name, rtype, level in system_roles:
            obj, _ = Role.objects.get_or_create(
                role_type=rtype,
                institution=institution,
                defaults={
                    "name": name,
                    "hierarchy_level": level,
                    "is_system_role": True,
                },
            )
            created.setdefault("roles", []).append(obj)

    # Sequence generators (student, employee)
    if SequenceGenerator:
        seqs = [
            ("student_id", f"{institution.code}-STU-", 3),
            ("employee_id", f"{institution.code}-EMP-", 3),
        ]
        for seq_type, prefix, padding in seqs:
            obj, _ = SequenceGenerator.objects.get_or_create(
                sequence_type=seq_type,
                institution=institution,
                defaults={"prefix": prefix, "padding": padding},
            )
            created.setdefault("sequences", []).append(obj)

    # Some basic system config entries
    try:
        SystemConfig = apps.get_model("core", "SystemConfig")
        cfg, _ = SystemConfig.objects.get_or_create(
            key=f"{institution.code}_defaults",
            defaults={
                "value": {"default_language": "en", "timezone": "UTC"},
                "config_type": "general",
            },
        )
        created.setdefault("system_configs", []).append(cfg)
    except Exception:
        pass

    return created


def populate_academics_for_institution(
    institution, min_students=10, departments=3, subjects=3, classes=2
):
    """Create sessions, departments, subjects, gradelevels, classes, teachers and students for an institution."""
    from django.apps import apps
    from django.utils import timezone
    import datetime

    AcademicSession = apps.get_model("academics", "AcademicSession")
    Department = apps.get_model("academics", "Department")
    Subject = apps.get_model("academics", "Subject")
    Class = apps.get_model("academics", "Class")
    GradeLevel = apps.get_model("academics", "GradeLevel")
    Student = apps.get_model("academics", "Student")
    Teacher = apps.get_model("academics", "Teacher")
    Enrollment = apps.get_model("academics", "Enrollment")
    User = get_user_model()
    InstitutionUser = apps.get_model("core", "InstitutionUser")

    from django.db import IntegrityError

    # Create a current academic session if none (session is per-institution)
    today = timezone.now().date()
    session, _ = AcademicSession.objects.get_or_create(
        institution=institution,
        name=f"Session {today.year}",
        defaults={
            "start_date": today.replace(month=1, day=1),
            "end_date": today.replace(month=12, day=31),
            "is_current": True,
            "number_of_semesters": 2,
        },
    )

    # Grade level
    # GradeLevel is a global model (GlobalBaseModel) so don't pass institution
    grade, _ = GradeLevel.objects.get_or_create(
        code=f"{institution.code}-G1",
        defaults={"name": "Grade 1", "education_stage": "elementary"},
    )

    # Departments
    dept_objs = []
    for i in range(1, departments + 1):
        dname = f"{institution.code}-Dept-{i}"
        dept, _ = Department.objects.get_or_create(
            institution=institution, code=dname, defaults={"name": dname}
        )
        dept_objs.append(dept)

    # Subjects - distribute across departments
    subj_objs = []
    for i in range(1, subjects + 1):
        sname = f"{institution.code}-Subject-{i}"
        dept = dept_objs[(i - 1) % len(dept_objs)]
        subj, _ = Subject.objects.get_or_create(
            institution=institution,
            code=f"{institution.code}-SUB-{i}",
            defaults={"name": sname, "department": dept},
        )
        subj_objs.append(subj)

    # Classes
    class_objs = []
    for i in range(1, classes + 1):
        cname = f"{institution.code}-Class-{i}"
        try:
            cls, _ = Class.objects.get_or_create(
                institution=institution,
                code=f"{institution.code}-CLS-{i}",
                defaults={
                    "name": cname,
                    "grade_level": grade,
                    "academic_session": session,
                },
            )
        except IntegrityError:
            # If a unique constraint on (grade_level, class_type, academic_session)
            # triggered, attempt to find an existing class with the same
            # grade_level and academic_session and reuse it.
            cls = Class.objects.filter(
                grade_level=grade, academic_session=session
            ).first()
            if not cls:
                # re-raise if we couldn't resolve
                raise
        class_objs.append(cls)

    # Create minimal teacher users and teacher profiles so assignments can reference them
    teacher_objs = []
    for i in range(1, max(2, subjects)):
        email = f"{institution.code}.teacher{i}@example.com"
        user, created = User.objects.get_or_create(
            email=email, defaults={"first_name": f"Teach{i}", "is_active": True}
        )
        if created:
            user.set_password("password")
            user.save()
        # InstitutionUser
        try:
            InstitutionUser.objects.get_or_create(
                user=user, institution=institution, defaults={"is_primary": False}
            )
        except Exception:
            pass
        # create Teacher profile
        try:
            t, _ = Teacher.objects.get_or_create(
                institution=institution,
                user=user,
                defaults={
                    "teacher_id": f"{institution.code}-T{i}",
                    "employee_id": f"{institution.code}-E{i}",
                    "joining_date": today,
                    "gender": "male",
                },
            )
            teacher_objs.append(t)
        except Exception:
            pass

    # Create students
    created_students = []
    for i in range(1, min_students + 1):
        email = f"{institution.code}.student{i}@example.com"
        user, created = User.objects.get_or_create(
            email=email, defaults={"first_name": f"Stud{i}", "is_active": True}
        )
        if created:
            user.set_password("password")
            user.save()
        try:
            InstitutionUser.objects.get_or_create(
                user=user, institution=institution, defaults={"is_primary": False}
            )
        except Exception:
            pass

        # Minimal student fields
        from datetime import date

        dob = date(today.year - 10, 1, 1)
        try:
            student, _ = Student.objects.get_or_create(
                institution=institution,
                user=user,
                defaults={
                    "admission_number": f"{institution.code}-ADM-{i}",
                    "admission_date": today,
                    "date_of_birth": dob,
                    "gender": "female",
                },
            )
            created_students.append(student)
        except Exception as e:
            print("student creation error", e)
            continue

        # Enroll to classes round-robin
        try:
            class_assigned = class_objs[(i - 1) % len(class_objs)]
            Enrollment.objects.get_or_create(
                institution=institution,
                student=student,
                class_enrolled=class_assigned,
                academic_session=session,
                defaults={"enrollment_date": today, "roll_number": i},
            )
        except Exception:
            pass

    # Create a basic exam type and exams/assignments
    try:
        ExamType = apps.get_model("assessment", "ExamType")
        Exam = apps.get_model("assessment", "Exam")
        Assignment = apps.get_model("assessment", "Assignment")
        # ExamType is global (no institution field)
        exam_type, _ = ExamType.objects.get_or_create(
            code=f"{institution.code}-UNIT",
            defaults={"name": "Unit Test", "weightage": 10},
        )
        # create one exam per class-subject
        for cls in class_objs:
            for subj in subj_objs:
                try:
                    ex, _ = Exam.objects.get_or_create(
                        institution=institution,
                        code=f"{institution.code}-EX-{cls.code}-{subj.code}",
                        defaults={
                            "name": f"Exam {cls.name} {subj.name}",
                            "exam_type": exam_type,
                            "academic_class": cls,
                            "subject": subj,
                            "exam_date": today,
                            "start_time": datetime.time(9, 0),
                            "end_time": datetime.time(10, 0),
                            "total_marks": 100,
                            "passing_marks": 40,
                        },
                    )
                except Exception:
                    pass
                try:
                    Assignment.objects.get_or_create(
                        institution=institution,
                        title=f"{cls.name} - {subj.name} Assignment",
                        defaults={
                            "subject": subj,
                            "teacher": teacher_objs[0] if teacher_objs else None,
                            "academic_session": session,
                            "total_marks": 100,
                            "due_date": timezone.now() + datetime.timedelta(days=7),
                            "publish_date": timezone.now(),
                        },
                    )
                except Exception:
                    pass
                # Create a question bank and sample questions for this class-subject
                try:
                    QuestionBank = apps.get_model("assessment", "QuestionBank")
                    Question = apps.get_model("assessment", "Question")
                    QuestionOption = apps.get_model("assessment", "QuestionOption")

                    qb_name = f"{institution.code} - {cls.name} - {subj.name} Bank"
                    qb, _ = QuestionBank.objects.get_or_create(
                        institution=institution,
                        subject=subj,
                        academic_class=cls,
                        name=qb_name,
                        defaults={
                            "description": f"Auto-generated question bank for {cls.name} {subj.name}",
                            "bank_type": "question_bank",
                            "difficulty_level": "easy",
                        },
                    )

                    # create 3 simple MCQs
                    for q_i in range(1, 4):
                        qtext = f"What is {q_i} + {q_i}?"
                        qobj, _ = Question.objects.get_or_create(
                            institution=institution,
                            question_bank=qb,
                            question_text=qtext,
                            defaults={
                                "question_type": "multiple_choice",
                                "marks": 1,
                                "difficulty_level": "easy",
                            },
                        )

                        # create 4 options, first one correct (2*q_i)
                        opts = [
                            str(2 * q_i),
                            str(2 * q_i + 1),
                            str(2 * q_i - 1),
                            str(2 * q_i + 2),
                        ]
                        for idx, opt_text in enumerate(opts, start=1):
                            QuestionOption.objects.get_or_create(
                                institution=institution,
                                question=qobj,
                                order=idx,
                                defaults={
                                    "option_text": opt_text,
                                    "is_correct": idx == 1,
                                },
                            )
                except Exception:
                    pass
    except Exception:
        pass

    return {
        "departments": dept_objs,
        "subjects": subj_objs,
        "classes": class_objs,
        "students": created_students,
    }

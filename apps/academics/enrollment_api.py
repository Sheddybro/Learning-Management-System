"""School-scoped supporting endpoints for the enrollment form."""

import json
from uuid import UUID

from django.http import JsonResponse
from django.views import View

from apps.core.middleware import get_current_institution
from apps.core.mixins import StaffRequiredMixin

from .models import AcademicSession, Class, Enrollment, Student


class EnrollmentApiView(StaffRequiredMixin, View):
    def school(self):
        return get_current_institution()

    def lookup(self, model, value):
        if not self.school() or not value:
            return None
        try:
            UUID(str(value))
            return model.objects.filter(pk=value, institution=self.school()).first()
        except (ValueError, TypeError):
            return None


class AvailableStudentView(EnrollmentApiView):
    def get(self, request):
        student = self.lookup(Student, request.GET.get("student_id"))
        if not student:
            return JsonResponse({"success": False, "message": "Student not found"}, status=404)
        name = student.user.get_full_name() or student.user.email
        return JsonResponse({"success": True, "student": {
            "id": str(student.pk), "student_id": student.student_id,
            "full_name": name, "initials": student.user.get_initials(),
            "status": student.status,
            "grade_level": "",
        }})


class EnrollmentSessionInfoView(EnrollmentApiView):
    def get(self, request):
        session = self.lookup(AcademicSession, request.GET.get("session_id"))
        if not session:
            return JsonResponse({"success": False, "message": "Session not found"}, status=404)
        return JsonResponse({"success": True, "session_info": {
            "id": str(session.pk), "name": session.name,
        }})


class AvailableClassesView(EnrollmentApiView):
    def get(self, request):
        session = self.lookup(AcademicSession, request.GET.get("session_id"))
        if not session:
            return JsonResponse({"success": False, "message": "Session not found"}, status=404)
        classes = Class.objects.filter(institution=self.school(), academic_session=session).select_related(
            "grade_level", "class_teacher__user"
        )
        data = []
        for school_class in classes:
            current_students = school_class.enrollments.filter(enrollment_status="active").count()
            data.append({
                "id": str(school_class.pk), "name": school_class.name,
                "grade_level": school_class.grade_level.name if school_class.grade_level else "",
                "class_type": school_class.get_class_type_display(),
                "capacity": school_class.capacity, "current_students": current_students,
                "teacher": school_class.class_teacher.user.get_full_name() if school_class.class_teacher else "",
            })
        return JsonResponse({"success": True, "classes": data})


class CheckRollNumberView(EnrollmentApiView):
    def post(self, request):
        try:
            payload = json.loads(request.body)
            roll_number = int(payload.get("roll_number"))
        except (ValueError, TypeError, json.JSONDecodeError):
            return JsonResponse({"available": False, "message": "Invalid roll number"}, status=400)
        school_class = self.lookup(Class, payload.get("class_id"))
        session = self.lookup(AcademicSession, payload.get("session_id"))
        if not school_class or not session or school_class.academic_session_id != session.pk:
            return JsonResponse({"available": False, "message": "Invalid class or session"}, status=400)
        if roll_number < 1:
            return JsonResponse({"available": False, "message": "Roll number must be positive"}, status=400)
        existing = Enrollment.objects.filter(
            institution=self.school(), class_enrolled=school_class,
            academic_session=session, roll_number=roll_number,
        )
        enrollment = self.lookup(Enrollment, payload.get("enrollment_id"))
        if enrollment:
            existing = existing.exclude(pk=enrollment.pk)
        available = not existing.exists()
        return JsonResponse({"available": available, "message": "Roll number already taken" if not available else ""})

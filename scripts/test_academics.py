from .utils import (
    setup_django,
    populate_academics_for_institution,
    populate_superadmin_entities_for_institution,
    create_superadmin,
)
from django.test import Client
import importlib
from django import forms as django_forms

setup_django()

client = Client()


def exercise_views():
    """Attempt GET requests for all academics URLs defined in the app's urls.py."""
    try:
        urls_mod = importlib.import_module("apps.academics.urls")
    except Exception as e:
        print("Could not import academics.urls:", e)
        return

    patterns = getattr(urls_mod, "urlpatterns", [])
    paths = []
    for p in patterns:
        try:
            # pattern is a django.urls.path object; .pattern.describe() may be complex.
            # We'll try to build a few representative GET URLs by replacing converters with dummy values
            raw = str(p.pattern)
        except Exception:
            continue
        # substitute common converters
        example = raw
        example = example.replace("<uuid:pk>", "00000000-0000-0000-0000-000000000000")
        example = example.replace(
            "<uuid:student_id>", "00000000-0000-0000-0000-000000000001"
        )
        example = example.replace(
            "<uuid:class_id>", "00000000-0000-0000-0000-000000000002"
        )
        example = example.replace(
            "<uuid:class_id>/", "00000000-0000-0000-0000-000000000002/"
        )
        example = example.replace("<uuid:pk>/", "00000000-0000-0000-0000-000000000000/")
        example = example.replace("<int:pk>", "1")
        example = example.lstrip("^").rstrip("$")
        paths.append("/academics/" + example)

    # Deduplicate and request
    # Ensure we are authenticated to avoid AnonymousUser attribute errors
    try:
        admin = create_superadmin()
        client.force_login(admin)
    except Exception:
        pass

    for path in sorted(set(paths)):
        # only GET - some urls may require auth; we still attempt
        try:
            resp = client.get(path)
            print("GET", path, "->", resp.status_code)
        except Exception as e:
            print("Error GET", path, e)


def exercise_forms():
    """Import and instantiate every form in apps.academics.forms."""
    try:
        forms_mod = importlib.import_module("apps.academics.forms")
    except Exception as e:
        print("Could not import academics.forms:", e)
        return

    for name in dir(forms_mod):
        obj = getattr(forms_mod, name)
        try:
            if isinstance(obj, type) and issubclass(
                obj, (django_forms.Form, django_forms.ModelForm)
            ):
                try:
                    inst = obj()
                    print("Instantiated form", name)
                except Exception as e:
                    print("Could not instantiate form", name, e)
        except Exception:
            continue


def run_for_institution(inst):
    print("=== academics tests for", getattr(inst, "name", inst), "===")
    # populate academics data where possible
    try:
        populate_superadmin_entities_for_institution(inst)
    except Exception as e:
        print("superadmin populate error", e)

    try:
        populate_academics_for_institution(inst)
    except Exception as e:
        print("populate academics error", e)

    # Ensure test client user has institution membership and a teacher profile
    try:
        admin = create_superadmin()
        from django.apps import apps
        from django.utils import timezone

        InstitutionUser = apps.get_model("core", "InstitutionUser")
        Teacher = apps.get_model("academics", "Teacher")
        Institution = apps.get_model("core", "Institution")

        # Resolve institution instance
        inst_obj = None
        if hasattr(inst, "pk"):
            inst_obj = inst
        else:
            # try to find by code or name
            try:
                inst_obj = Institution.objects.filter(
                    name=getattr(inst, "name", str(inst))
                ).first()
            except Exception:
                inst_obj = Institution.objects.first()

        if inst_obj:
            InstitutionUser.objects.get_or_create(
                user=admin, institution=inst_obj, defaults={"is_primary": True}
            )

            # Create a minimal Teacher profile if not present
            if not getattr(admin, "teacher_profile", None):
                try:
                    Teacher.objects.get_or_create(
                        institution=inst_obj,
                        user=admin,
                        defaults={
                            "teacher_id": f"{inst_obj.code}-ADMIN-T",
                            "employee_id": f"{inst_obj.code}-ADMIN-E",
                            "joining_date": timezone.now().date(),
                            "gender": "male",
                        },
                    )
                except Exception:
                    pass

        client.force_login(admin)
    except Exception:
        pass

    exercise_forms()
    exercise_views()


if __name__ == "__main__":
    # allow running directly
    run_for_institution({"name": "LocalTest"})

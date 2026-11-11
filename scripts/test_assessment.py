from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("assessment: running checks for", getattr(inst, "name", inst))
    try:
        from apps.assessment import models as m

        print(
            "assessment models loaded:",
            [name for name in dir(m) if name[0].isupper()][:10],
        )
    except Exception as e:
        print("assessment import error", e)

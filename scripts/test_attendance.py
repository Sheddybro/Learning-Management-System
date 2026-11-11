from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("attendance: basic import for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.attendance")
        print("attendance imported")
    except Exception as e:
        print("attendance import error", e)

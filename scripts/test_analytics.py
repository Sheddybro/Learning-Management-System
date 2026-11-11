from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("analytics: basic import for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.analytics")
        print("analytics imported")
    except Exception as e:
        print("analytics import error", e)

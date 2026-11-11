from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("core: running checks for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.core")
        print("core imported")
    except Exception as e:
        print("core import error", e)

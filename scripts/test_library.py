from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("library: basic import for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.library")
    except Exception as e:
        print("library import error", e)

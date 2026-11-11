from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("audit: basic import for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.audit")
    except Exception as e:
        print("audit import error", e)

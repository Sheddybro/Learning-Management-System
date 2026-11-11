from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("support: basic import for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.support")
    except Exception as e:
        print("support import error", e)

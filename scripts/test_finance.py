from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("finance: basic import for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.finance")
    except Exception as e:
        print("finance import error", e)

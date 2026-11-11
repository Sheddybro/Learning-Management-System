from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("hostels: basic import for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.hostels")
    except Exception as e:
        print("hostels import error", e)

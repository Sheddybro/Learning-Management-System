from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("health: basic import for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.health")
    except Exception as e:
        print("health import error", e)

from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("transport: basic import for", getattr(inst, "name", inst))
    try:
        import importlib

        importlib.import_module("apps.transport")
    except Exception as e:
        print("transport import error", e)

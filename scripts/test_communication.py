from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("communication: create sample data for", getattr(inst, "name", inst))
    try:
        from apps.communication import models as m

        for name in dir(m):
            cls = getattr(m, name)
            try:
                if hasattr(cls, "objects"):
                    obj = cls()
                    try:
                        obj.save()
                        print("Created", cls.__name__)
                    except Exception:
                        pass
                    break
            except Exception:
                continue
    except Exception as e:
        print("communication error", e)

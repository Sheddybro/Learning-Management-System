from .utils import setup_django

setup_django()


def run_for_institution(inst):
    print("activities: running lightweight checks for", getattr(inst, "name", inst))
    try:
        from apps.activities import models as m

        # try to create a sample record for first model if possible
        for attr in dir(m):
            cls = getattr(m, attr)
            try:
                if hasattr(cls, "objects"):
                    # attempt to create with minimal defaults if possible
                    obj = cls()
                    try:
                        obj.save()
                        print("Created sample", cls.__name__)
                    except Exception:
                        pass
                    break
            except Exception:
                continue
    except Exception as e:
        print("activities import error", e)

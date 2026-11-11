from .utils import setup_django, create_superadmin

setup_django()


def run_for_institution(inst):
    print("users: ensuring superadmin for", getattr(inst, "name", inst))
    try:
        admin = create_superadmin()
        print("Superadmin exists:", admin.username)
    except Exception as e:
        print("users error", e)

from .utils import setup_django, create_superadmin, ensure_site_entities
from .utils import create_institution


def main():
    """Run all per-app test scripts for three institutions."""
    setup_django()

    # Basic superadmin / site setup
    create_superadmin()
    ensure_site_entities()

    # Create three institutions and run per-app scripts for each
    institutions = []
    from django.db import transaction
    from django.apps import apps

    # Look for an Institution-like model across installed apps
    inst_model = None
    for label in apps.app_configs:
        try:
            m = apps.get_model(label, "Institution")
            inst_model = m
            break
        except LookupError:
            continue

    if inst_model is None:
        print(
            "No `Institution` model found. Per-institution tests will use generic site context."
        )

    for i in range(1, 4):
        name = f"Test Institution {i}"
        code = f"TEST{i}"
        if inst_model:
            obj = create_institution(name, code)
            institutions.append(obj)
            print("Created institution:", obj)
        else:
            institutions.append({"name": name})
            print("Added pseudo-institution:", name)

    # Import per-app scripts and run their `run_for_institution` function if present
    import importlib

    app_names = [
        cfg.name for cfg in apps.get_app_configs() if cfg.name.startswith("apps.")
    ]

    for app in app_names:
        module_name = f'scripts.test_{app.split(".")[-1]}'
        try:
            mod = importlib.import_module(module_name)
        except ModuleNotFoundError:
            # skip missing scripts
            continue
        run_fn = getattr(mod, "run_for_institution", None)
        if callable(run_fn):
            for inst in institutions:
                print(f'Running {module_name} for {getattr(inst, "name", inst)}')
                try:
                    with transaction.atomic():
                        run_fn(inst)
                except Exception as e:
                    print("Error running", module_name, e)

    print("All scripts executed (see output).")


if __name__ == "__main__":
    main()

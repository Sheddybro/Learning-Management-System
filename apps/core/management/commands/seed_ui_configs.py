#!/usr/bin/env python
"""
Management command to seed default UI configuration settings.
"""

from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _

from apps.core.models import SystemConfig


class Command(BaseCommand):
    help = "Seed default UI configuration settings for the system"

    def handle(self, *args, **options):
        """Create default UI configuration entries."""
        self.stdout.write(self.style.SUCCESS(_("Seeding UI configurations...")))

        # Default UI configurations
        ui_configs = [
            # Color Scheme
            {
                "key": "ui_primary_color",
                "value": "#0d6efd",
                "description": "Primary brand color used throughout the interface",
                "config_type": "ui",
            },
            {
                "key": "ui_secondary_color",
                "value": "#6c757d",
                "description": "Secondary color for complementary elements",
                "config_type": "ui",
            },
            {
                "key": "ui_success_color",
                "value": "#198754",
                "description": "Success state color (green)",
                "config_type": "ui",
            },
            {
                "key": "ui_danger_color",
                "value": "#dc3545",
                "description": "Error/danger state color (red)",
                "config_type": "ui",
            },
            {
                "key": "ui_warning_color",
                "value": "#ffc107",
                "description": "Warning state color (yellow)",
                "config_type": "ui",
            },
            {
                "key": "ui_info_color",
                "value": "#0dcaf0",
                "description": "Info state color (cyan)",
                "config_type": "ui",
            },
            {
                "key": "ui_accent_color",
                "value": "#6610f2",
                "description": "Accent color for highlights and special elements",
                "config_type": "ui",
            },
            # Typography
            {
                "key": "ui_font_family_primary",
                "value": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                "description": "Primary font family for body text and general content",
                "config_type": "ui",
            },
            {
                "key": "ui_font_family_secondary",
                "value": "'Poppins', sans-serif",
                "description": "Secondary font family for headings and special text",
                "config_type": "ui",
            },
            {
                "key": "ui_font_size_base",
                "value": "1rem",
                "description": "Base font size for the interface",
                "config_type": "ui",
            },
            {
                "key": "ui_font_weight_normal",
                "value": "400",
                "description": "Normal font weight",
                "config_type": "ui",
            },
            {
                "key": "ui_font_weight_bold",
                "value": "600",
                "description": "Bold font weight",
                "config_type": "ui",
            },
            {
                "key": "ui_line_height_base",
                "value": "1.5",
                "description": "Base line height for text",
                "config_type": "ui",
            },
            # Spacing
            {
                "key": "ui_border_radius",
                "value": "0.375rem",
                "description": "Default border radius for components",
                "config_type": "ui",
            },
            {
                "key": "ui_border_radius_sm",
                "value": "0.25rem",
                "description": "Small border radius",
                "config_type": "ui",
            },
            {
                "key": "ui_border_radius_lg",
                "value": "0.5rem",
                "description": "Large border radius",
                "config_type": "ui",
            },
            {
                "key": "ui_spacing_unit",
                "value": "1rem",
                "description": "Base spacing unit for margins and padding",
                "config_type": "ui",
            },
            # Shadows
            {
                "key": "ui_shadow_sm",
                "value": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
                "description": "Small shadow for subtle elevation",
                "config_type": "ui",
            },
            {
                "key": "ui_shadow",
                "value": "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)",
                "description": "Default shadow for cards and components",
                "config_type": "ui",
            },
            {
                "key": "ui_shadow_lg",
                "value": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
                "description": "Large shadow for modals and dropdowns",
                "config_type": "ui",
            },
            {
                "key": "ui_shadow_xl",
                "value": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
                "description": "Extra large shadow for overlays",
                "config_type": "ui",
            },
            # Component Specific
            {
                "key": "ui_header_height",
                "value": "80px",
                "description": "Height of the main header/navigation bar",
                "config_type": "ui",
            },
            {
                "key": "ui_sidebar_width",
                "value": "280px",
                "description": "Width of the sidebar navigation",
                "config_type": "ui",
            },
            {
                "key": "ui_container_max_width",
                "value": "1200px",
                "description": "Maximum width of main content containers",
                "config_type": "ui",
            },
            {
                "key": "ui_transition_duration",
                "value": "0.3s",
                "description": "Default transition duration for animations",
                "config_type": "ui",
            },
            {
                "key": "ui_transition_easing",
                "value": "ease-in-out",
                "description": "Default easing function for transitions",
                "config_type": "ui",
            },
            # Dark Theme Colors (for dark mode overrides)
            {
                "key": "ui_dark_primary_color",
                "value": "#6ea8fe",
                "description": "Primary color for dark theme",
                "config_type": "ui",
            },
            {
                "key": "ui_dark_secondary_color",
                "value": "#a7acb1",
                "description": "Secondary color for dark theme",
                "config_type": "ui",
            },
            {
                "key": "ui_dark_bg_color",
                "value": "#212529",
                "description": "Background color for dark theme",
                "config_type": "ui",
            },
            {
                "key": "ui_dark_surface_color",
                "value": "#343a40",
                "description": "Surface/card color for dark theme",
                "config_type": "ui",
            },
            {
                "key": "ui_dark_text_color",
                "value": "#dee2e6",
                "description": "Primary text color for dark theme",
                "config_type": "ui",
            },
            {
                "key": "ui_dark_text_muted",
                "value": "#adb5bd",
                "description": "Muted text color for dark theme",
                "config_type": "ui",
            },
            # Layout Options
            {
                "key": "ui_enable_rounded_corners",
                "value": True,
                "description": "Enable rounded corners throughout the interface",
                "config_type": "ui",
            },
            {
                "key": "ui_enable_shadows",
                "value": True,
                "description": "Enable shadows for depth and elevation",
                "config_type": "ui",
            },
            {
                "key": "ui_enable_animations",
                "value": True,
                "description": "Enable smooth transitions and animations",
                "config_type": "ui",
            },
            {
                "key": "ui_compact_mode",
                "value": False,
                "description": "Use compact spacing and sizing for denser layouts",
                "config_type": "ui",
            },
        ]

        created_count = 0
        updated_count = 0

        for config_data in ui_configs:
            config, created = SystemConfig.objects.get_or_create(
                key=config_data["key"],
                defaults={
                    "value": config_data["value"],
                    "config_type": config_data["config_type"],
                    "description": config_data["description"],
                    "is_public": True,
                    "allows_institution_override": True,
                    "status": "active",
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(_("Created UI config: {}").format(config.key))
                )
            else:
                # Always update existing config to ensure it's correct
                config.value = config_data["value"]
                config.description = config_data["description"]
                config.config_type = config_data["config_type"]
                config.is_public = True
                config.allows_institution_override = True
                config.status = "active"
                config.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(_("Updated UI config: {}").format(config.key))
                )

        self.stdout.write(
            self.style.SUCCESS(
                _(
                    "UI configuration seeding completed. Created: {}, Updated: {}"
                ).format(created_count, updated_count)
            )
        )

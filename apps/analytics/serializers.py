# apps/analytics/serializers.py

from rest_framework import serializers
from .models import Report, KPI, Dashboard


class ReportSerializer(serializers.ModelSerializer):
    """
    Serializer for Report model.
    """
    report_type_name = serializers.CharField(source='report_type.name', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True)
    academic_session_name = serializers.CharField(source='academic_session.name', read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'name', 'report_type', 'report_type_name', 'academic_session',
            'academic_session_name', 'generated_by', 'generated_by_name',
            'parameters', 'status', 'created_at', 'generation_started_at',
            'generation_completed_at', 'summary', 'format', 'file_size'
        ]
        read_only_fields = ['id', 'created_at', 'generation_started_at', 'generation_completed_at']


class KPISerializer(serializers.ModelSerializer):
    """
    Serializer for KPI model.
    """
    latest_value = serializers.SerializerMethodField()
    latest_measurement_date = serializers.SerializerMethodField()

    class Meta:
        model = KPI
        fields = [
            'id', 'name', 'code', 'description', 'category', 'value_type',
            'target_value', 'refresh_frequency', 'is_trending', 'status',
            'created_at', 'updated_at', 'latest_value', 'latest_measurement_date'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_latest_value(self, obj):
        """Get the latest measured value for this KPI."""
        latest_measurement = obj.measurements.order_by('-measured_at').first()
        return latest_measurement.value if latest_measurement else None

    def get_latest_measurement_date(self, obj):
        """Get the date of the latest measurement."""
        latest_measurement = obj.measurements.order_by('-measured_at').first()
        return latest_measurement.measured_at if latest_measurement else None


class DashboardSerializer(serializers.ModelSerializer):
    """
    Serializer for Dashboard model.
    """
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)

    class Meta:
        model = Dashboard
        fields = [
            'id', 'name', 'description', 'owner', 'owner_name', 'dashboard_type',
            'layout_config', 'widget_config', 'refresh_interval', 'is_default',
            'is_public', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Ensure owner is set to current user."""
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)

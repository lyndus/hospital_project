from rest_framework import serializers
from .models import *
import re
from django.utils import timezone


# ========================
# USER SERIALIZER
# ========================
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'email', 'phone', 'address', 'role'
        ]

    def validate_email(self, value):
        if value and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError("Enter a valid email address.")
        return value.lower() if value else value

    def validate_phone(self, value):
        if value:
            cleaned = re.sub(r'[\s\-]', '', value)
            if not cleaned.isdigit():
                raise serializers.ValidationError("Phone number must contain digits only.")
            if not (7 <= len(cleaned) <= 15):
                raise serializers.ValidationError("Phone number must be between 7 and 15 digits.")
        return value

    def validate_first_name(self, value):
        if value and not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', value):
            raise serializers.ValidationError("First name must contain letters only.")
        return value

    def validate_last_name(self, value):
        if value and not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', value):
            raise serializers.ValidationError("Last name must contain letters only.")
        return value


# ========================
# SERVICE SERIALIZER
# ========================
class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'

    def validate_name(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Service name must be at least 2 characters.")
        return value


# ========================
# DOCTOR SERIALIZER
# ========================
class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = '__all__'

    def validate_grade(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Grade must be at least 2 characters.")
        return value


# ========================
# PATIENT SERIALIZER
# ========================
class PatientSerializer(serializers.ModelSerializer):
    guardian_full_name = serializers.SerializerMethodField(read_only=True)
    created_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Patient
        fields = '__all__'

    def get_guardian_full_name(self, obj):
        return f"{obj.guardian.first_name} {obj.guardian.last_name}"

    def get_created_by_name(self, obj):
        return f"Dr. {obj.created_by.user.first_name} {obj.created_by.user.last_name}"

    def validate_patient_first_name(self, value):
        if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', value):
            raise serializers.ValidationError("First name must contain letters only.")
        return value

    def validate_patient_last_name(self, value):
        if not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', value):
            raise serializers.ValidationError("Last name must contain letters only.")
        return value

    def validate_patient_date_of_birth(self, value):
        if value >= timezone.now().date():
            raise serializers.ValidationError("Date of birth must be in the past.")
        return value

    def validate_gender(self, value):
        if value not in ['male', 'female']:
            raise serializers.ValidationError("Gender must be male or female.")
        return value

# ========================
# MEDICAL FILE SERIALIZER
# ========================
class MedicalFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalFile
        fields = '__all__'
        read_only_fields = ['patient', 'created_at', 'last_edited_by', 'last_edited_at' ]

    def validate_height(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Height must be a positive number.")
        if value is not None and value > 300:
            raise serializers.ValidationError("Height cannot exceed 300 cm.")
        return value

    def validate_weight(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Weight must be a positive number.")
        if value is not None and value > 500:
            raise serializers.ValidationError("Weight cannot exceed 500 kg.")
        return value

    def validate_blood_type(self, value):
        valid_types = ['a+', 'a-', 'b+', 'b-', 'o+', 'o-', 'ab+', 'ab-']
        if value and value not in valid_types:
            raise serializers.ValidationError(f"Blood type must be one of: {', '.join(valid_types)}")
        return value


# ========================
# DOCUMENT SERIALIZER
# ========================
class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ['file', 'uploaded_by', 'service', 'uploaded_at']

    def validate_file_path(self, value):
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
        file_name = value.name.lower()
        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError(
                f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value

    def validate_file_name(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("File name must be at least 2 characters.")
        return value


# ========================
# SCHEDULE SERIALIZER
# ========================
class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = '__all__'

    def validate_max_appointments(self, value):
        if value <= 0:
            raise serializers.ValidationError("Max appointments must be a positive number.")
        if value > 100:
            raise serializers.ValidationError("Max appointments cannot exceed 100.")
        return value

    def validate(self, data):
        start = data.get('start_time')
        end = data.get('end_time')
        if start and end and start >= end:
            raise serializers.ValidationError("Start time must be before end time.")
        return data

# ========================
# APPOINTMENT SERIALIZER
# ========================
class AppointmentSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(write_only=True, required=False)
    doctor_full_name = serializers.SerializerMethodField(read_only=True)
    service_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Appointment
        fields = '__all__'
        read_only_fields = ['queue_number', 'qr_code', 'service', 'doctor']

    def get_doctor_full_name(self, obj):
        return f"Dr. {obj.doctor.user.first_name} {obj.doctor.user.last_name}"

    def get_service_name(self, obj):
        return obj.service.name

    def validate_guest_phone(self, value):
        if value:
            cleaned = re.sub(r'[\s\-]', '', value)
            if not cleaned.isdigit():
                raise serializers.ValidationError("Phone number must contain digits only.")
            if not (7 <= len(cleaned) <= 15):
                raise serializers.ValidationError("Phone number must be between 7 and 15 digits.")
        return value

    def validate_guest_first_name(self, value):
        if value and not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', value):
            raise serializers.ValidationError("First name must contain letters only.")
        return value

    def validate_guest_last_name(self, value):
        if value and not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', value):
            raise serializers.ValidationError("First name must contain letters only.")
        return value

    def validate_appointment_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Appointment date cannot be in the past.")
        return value

# ========================
# VACCINATION SERIALIZER
# ========================
class VaccinationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = VaccinationRecord
        fields = '__all__'
        read_only_fields = ['patient', 'administered_by']

    def validate_vaccine_name(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Vaccine name must be at least 2 characters.")
        return value

    def validate_date_administered(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Date administered cannot be in the future.")
        return value

    def validate_next_dose_date(self, value):
        if value and value < timezone.now().date():
            raise serializers.ValidationError("Next dose date cannot be in the past.")
        return value


# ========================
# ANNOUNCEMENT SERIALIZER
# ========================
class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = '__all__'
        read_only_fields = ['posted_by', 'published_at']

    def validate_content(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Announcement content must be at least 10 characters.")
        return value
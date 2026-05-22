import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

# ----------------------------
# Custom User
# ----------------------------
class User(AbstractUser):
    ROLE_CHOICES = [("admin", "Admin"), ("doctor", "Doctor"), ("guardian", "Guardian")]
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="guardian")
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"


# ----------------------------
# Service
# ----------------------------
class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# ----------------------------
# Doctor
# ----------------------------
class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    grade = models.CharField(max_length=21)

    def __str__(self):
        return f"Dr. {self.user.first_name} {self.user.last_name}"


# ----------------------------
# Announcement
# ----------------------------
class Announcement(models.Model):
    TARGET_CHOICES = [
        ("all", "All Users"),
        ("doctor", "Doctors"),
        ("guardian", "Guardians"),
        ("admin", "Admins"),
    ]
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    is_active = models.BooleanField(default=False)
    published_at = models.DateField(auto_now_add=True)
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, default="all")

    def __str__(self):
        return f"Announcement by {self.posted_by.get_full_name()} — {self.published_at}"


# ----------------------------
# Patient
# ----------------------------
class Patient(models.Model):
    GENDER_CHOICE = [
        ("female", "Female"),
        ("male", "Male"),
    ]
    guardian = models.ForeignKey(User, on_delete=models.PROTECT, limit_choices_to={"role": "guardian"})
    created_by = models.ForeignKey(Doctor, on_delete=models.PROTECT)
    patient_first_name = models.CharField(max_length=100)
    patient_last_name = models.CharField(max_length=100)
    patient_date_of_birth = models.DateField()
    gender = models.CharField(max_length=6, choices=GENDER_CHOICE)
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient_first_name} {self.patient_last_name}"


# ----------------------------
# MedicalFile
# ----------------------------
class MedicalFile(models.Model):
    BLOOD_CHOICES = [
        ("a+", "A+"), ("a-", "A-"), ("b+", "B+"), ("b-", "B-"),
        ("o+", "O+"), ("o-", "O-"), ("ab+", "AB+"), ("ab-", "AB-"),
    ]
    patient = models.OneToOneField(Patient, on_delete=models.PROTECT)
    created_at = models.DateField(auto_now_add=True)
    last_edited_by = models.ForeignKey(
        'Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='edited_files'
    )
    last_edited_at = models.DateTimeField(null=True, blank=True)
    height = models.DecimalField(max_digits=5, decimal_places=2)
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    blood_type = models.CharField(max_length=3, choices=BLOOD_CHOICES)
    allergies = models.TextField(blank=True, null=True)
    chronic_condition = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"patient {self.patient.patient_first_name} {self.patient.patient_last_name} in {self.created_at}"

# ----------------------------
# Document
# ----------------------------
class Document(models.Model):
    DOCUMENT_CHOICES = [
        ("ordonnance", "Ordonnance"),
        ("resultat_labo", "Résultat de labo"),
        ("resultat_efr", "Résultat EFR"),
        ("endoscopie", "Compte-rendu endoscopie"),
        ("radiologie", "Imagerie radiologique"),
        ("sortie", "Compte-rendu de sortie"),
        ("vaccination", "Carnet de vaccination"),
    ]
    file = models.ForeignKey(MedicalFile, on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(Doctor, on_delete=models.PROTECT)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    document_type = models.CharField(max_length=100, choices=DOCUMENT_CHOICES)
    file_name = models.CharField(max_length=255)
    file_path = models.FileField(upload_to="documents/")
    file_size = models.IntegerField(null=True, blank=True)
    is_visible = models.BooleanField(default=False)
    uploaded_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name}"

    def save(self, *args, **kwargs):
        if self.uploaded_by:
            self.service = self.uploaded_by.service
        super().save(*args, **kwargs)


# ----------------------------
# Schedule
# ----------------------------
class Schedule(models.Model):
    DAY_CHOICES = [
        ("sunday", "Sunday"), ("monday", "Monday"), ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"), ("thursday", "Thursday"),
        ("friday", "Friday"), ("saturday", "Saturday"),
    ]
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_appointments = models.IntegerField()

    def __str__(self):
        return f"schedule of Dr. {self.doctor.user.first_name}"


# ----------------------------
# Appointment
# ----------------------------
class Appointment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT)
    patient = models.ForeignKey(Patient, null=True, blank=True, on_delete=models.SET_NULL)
    guest_first_name = models.CharField(max_length=100)
    guest_last_name = models.CharField(max_length=100)
    guest_phone = models.CharField(max_length=20)
    appointment_date = models.DateField()
    queue_number = models.IntegerField()
    qr_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    appointment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.guest_first_name} {self.guest_last_name} — {self.appointment_date}"

    def clean(self):
        if not self.patient and not self.guest_first_name:
            raise ValidationError("Appointment must have a patient or guest info.")


# ----------------------------
# VaccinationRecord
# ----------------------------
class VaccinationRecord(models.Model):
    STATUS_CHOICES = [("administered", "Administered"), ("scheduled", "Scheduled")]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    administered_by = models.ForeignKey(Doctor, on_delete=models.PROTECT)
    vaccine_name = models.CharField(max_length=100)
    date_administered = models.DateField()
    next_dose_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="administered")

    def __str__(self):
        return f"{self.vaccine_name} by Dr. {self.administered_by.user.first_name}"
    
# Audit Log
# tracks all critical actions performed on medical data
# tracked models: Patient,MadicalFile,Document

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("created","Created"),
        ("updated","Updated"),
        ("deleted","Deleted"),
        ("visability_toggled","Visibility Toggle"),
    ]   
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    action =models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    record_id = models.IntegerField()
    notes = models.TextField(blank=True,null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.performed_by} {self.action} #{self.record_id}"
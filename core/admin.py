from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import (
    Service, User, Doctor, Patient,
    MedicalFile, Document, Schedule,
    Appointment, VaccinationRecord, Announcement,
)

# Register all models in admin
admin.site.register(Service)
admin.site.register(User)
admin.site.register(Doctor)
admin.site.register(Patient)
admin.site.register(MedicalFile)
admin.site.register(Document)
admin.site.register(Schedule)
admin.site.register(Appointment)
admin.site.register(VaccinationRecord)
admin.site.register(Announcement)
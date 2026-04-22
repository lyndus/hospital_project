#Query Reference Sheet

**Project:** Pediatric Department Management System
**Stack:** Django + PostgreSQL
**Total queries:** 35 across 8 models
**Last updated:** April 2026

# Patients
### Get all patients
**Description:** Retrieve all patients in the system (admin use)

```python
Patient.objects.all()
```

### Get doctor's patients
**Description:** Retrieve all patients created by a specific doctor

```python
Patient.objects.filter(created_by=doctor)
```

### Get guardian's children
**Description:** Retrieve all patients belonging to a guardian

```python
Patient.objects.filter(guardian=guardian)
```

### Search patient by name
**Description:** Case-insensitive search by first or last name

```python
from django.db.models import Q
Patient.objects.filter(
    Q(patient_first_name__icontains=query) |
    Q(patient_last_name__icontains=query)
)
```
# MedicalFile

### Get patient medical file
**Description:** Retrieve the single medical file for a given patient

```python
MedicalFile.objects.get(patient=patient) #oneToone field so get not filter 
```
### Get medicalfile with documents 
**Description:** Fetch a medical file and all it's linked documents in one query

```python
MedicalFile.objects.prefetch_related('document_set').get(patient=patient)
```
### Get patient with a specific bloodtype 
**Description:** Retrieve all medical files where bloodtype matches a given value
```python
MedicalFile.objects.filter(blood_type=blood_type)
```
### Get last activity on medical file 
**Description:** being able to know what doctor last edit the medical file  either from last added document or vaccination record this is the real last activity on medical file 
```python
#doc
lastest_doc=Document.objects.filter(file__patient=patient).order_by('-uploaded_at').select_related('uploaded_by__user').first()
#vaccination
lastest_vac=VaccinationRecord.objects.filter(patient=patient).order_by('-date_administered').select_related('administered_by__user').first() 
#comparison
if latest_doc and latest_vac:
    last_activity = latest_doc if latest_doc.uploaded_at.date() >= latest_vac.date_administered else latest_vac
elif latest_doc:
    last_activity=latest_doc
elif latest_vac:
    last_activity=latest_vac
else:
    last_activity=None
```

# Documents

### List all Documents for a patient 
**Description:** Retrieve all document belonging to a specefic patient (ordered by uploaddate-most recent)
```python
Document.objects.filter(file__patient=patient).order_by('-uploaded_at')
```
### Filter Documents by type
**Description:** Retrieve all documents of a specefic type for a given patient
```python
Document.objects.filter(file__patient=patient,document_type=document_type)
```
### Get Documents uploaded by a specefic Doctor
**Description:** Retrieve all documents that were uploaded by a doctor regardless of patient
```python
Document.objects.filter(uploaded_by=doctor).order_by('-uploaded_at')
```
### Count Documents per type for a patient 
**Description:** Return a summary count of documents grouped by type for a given patient
```python
from django.db.models import Count

Document.objects.filter(file__patient=patient).values('document_type').annotate(total=Count('id'))
```
### Exclude hidden documents
**Description:** Retrieve all documents in a patient's medical file that are not hidden from the guardian
```python
Document.objects.filter(file__patient=patient).exclude(is_visible=False)
```

# Appointments
### List all Appointment for a patient
**Description:**Retrieve all appointments belonging to a specefic patient,ordered by date(most recent first)
```python
Appointment.objects.filter(patient=patient).order_by('-appointment_date')
```
### List today's appointments for a doctor
**Description:** Retrieve all appointments scheduled for today for a specefic doctor,ordered by time
```python
from django.utils import timezone
today = timezone.now().date()
Appointment.objects.filter(doctor=doctor, appointment_date=today).order_by('appointment_date')
```
### Filter appointments by status
**Description**:Retrieve all appointments for a given patient filtered by status
```python
Appointment.objects.filter(patient=patient,appointment_status=appointment_status).order_by('-appointment_date')
```
### Get upcoming appointments across all patients
**Description:** Retrieve all appointment scheduled in the future 
```python
from django.utils import timezone
Appointment.objects.filter(appointment_date__gte=timezone.now().date()).order_by('appointment_date')
```
### Count appointments per doctor this week
**Description:** Return number of appointments for each doctors this week ordered by total,more precisely we will have a date then we will figure which day of the week it is then print the whole week,example(xxxx-xx-xx) date matches tuesday,and the week start from monday till sunday,so will print that whole week including tesday ( knowing the day is important bc it help us know the range of the search)
```python
from django.db.models import Count
from datetime import date, timedelta
today=date.today() # here we are using the present date, we can change it by the date we wanna search for 
monday = today - timedelta(days=today.weekday())
sunday = monday + timedelta(days=6)

Appointment.objects.filter(
    appointment_date__range=(monday,sunday)).values('doctor').annotate(total=Count('id')).order_by('-total')

```

### Exclude cancelled appointment
**Description:** Retrieve all appointments that are not cancelled, ordered by date
```python
Appointment.objects.exclude(appointment_status="cancelled").order_by('-appointment_date')
```


# Schedule
### Get a doctor's weekly schedule
**Description:**Retrieve all schedule slots for a specefic doctor for current week ordered by day (from monday to sunday)
```python
from django.db.models import Case, When, IntegerField

Schedule.objects.filter(doctor=doctor).annotate(
    day_order=Case(
        When(day_of_week="monday", then=1),
        When(day_of_week="tuesday", then=2),
        When(day_of_week="wednesday", then=3),
        When(day_of_week="thursday", then=4),
        When(day_of_week="friday", then=5),
        When(day_of_week="saturday", then=6),
        When(day_of_week="sunday", then=7),
        output_field=IntegerField(),
    )
).order_by("day_order")
```
### Check if a doctor is available on given day 
**Description:** Return is doctor work a specefic day or not 

```python
Schedule.objects.filter(doctor=doctor,day_of_week=day_of_week).exists()
```
### List all Doctors is available on given day
**Description:** Return list of all doctors working in specefic day

```python
Schedule.objects.filter(day_of_week=day_of_week).select_related('doctor').order_by('start_time')
```
### Get full schedule for all doctors in a service
**Description:** Retrieve all schedule slots belonging to doctors in a specific service

```python
Schedule.objects.filter(doctor__service=service).order_by('day_of_week','start_time')
```
### Exclude doctors with no schedule
**Description:** Retrieve all doctors who have at least one schedule entry defined (means the doctors that doesn't appear in schedule table)

```python
Doctor.objects.exclude(schedule__isnull=True)
```


# VaccinationRecord
### List all Vaccination records for patient 
**Description:** Retrieve all Vaccination records belonging to a specefic patient ordered by day(most recent first)
```python
VaccinationRecord.objects.filter(patient=patient).order_by('-date_administered')
```
### Get all Scheduled (upcoming) doses for a patient 
**Description:** Retrieve all VaccinationRecord records for a specefic patient( where status is "scheduled")
```python
VaccinationRecord.objects.filter(patient=patient,status="scheduled").order_by('next_dose_date')
```
### Get all Vaccination record administered by a doctor
**Description:** Retrieve all Vaccination record where a specefic doctor administered the vaccine,ordered by date 
```python
VaccinationRecord.objects.filter(administered_by=doctor).order_by('date_administered')
```
### List patients with an upcoming dose this week
**Description:** Retrieve all vaccination records where next dose is this week 
```python
from datetime import date, timedelta

today = date.today()
end_of_week = today + timedelta(days=7)
VaccinationRecord.objects.filter(next_dose_date__range=(today, end_of_week)).order_by('next_dose_date')
```
# Announcement
### List all active announcements
**Description:** Retrieve all announcements where it's active ordered by most recent 
```python
 Announcement.objects.filter(is_active = True).order_by('-published_at')
 ```
### Get the recent announcement ( about 5)
**Description:** Retrieve the 5 latest announcements (used for homepage/dashboard preview widget)
```python
Announcement.objects.filter(is_active = True).order_by('-published_at')[:5]
```
### Get all announcement posted by specific admin (we have just on admin but i will add for admin pannel)
**Description:** Retrieve all announcements posted by a specefic admin
```python
Announcement.objects.filter(posted_by=user).order_by('-published_at')
```
# Service
### List all doctor in a service
**Description:** Retrieve all doctors belonging to a specefic service
```python
Doctor.objects.filter(service=service)
```
### Get all appointments for a specefic service
**Description:** Retrieve all appointment where the doctor belongs to a specefic service ordered by date 
```python
Appointment.objects.filter(doctor__service=service).order_by('-appointment_date')
```
### Count patient per service
**Description:**Return the number of distinct patient having appointement in a specefic service 
```python
Appointment.objects.filter(doctor__service=service).values('patient').distinct().count()
```
### Get all vaccination records for a service 
**Description:** Retrieve all vaccination record where the administering doctor belong to a specefic service ordered by date 
```python
VaccinationRecord.objects.filter(administered_by__service=service).order_by('-date_administered')
```

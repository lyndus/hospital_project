from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Auth
    path('login/', views.login_view),

    # Services
    path('services/', views.service_list),
    path('services/create/', views.service_create),
    path('services/<int:pk>/', views.service_detail),
    path('services/<int:pk>/update/', views.service_update),
    path('services/<int:pk>/delete/', views.service_delete),

    # Doctors
    path('doctors/', views.doctor_list),
    path('doctors/create/', views.doctor_create),
    path('doctors/<int:pk>/', views.doctor_detail),
    path('doctors/<int:pk>/update/', views.doctor_update),
    path('doctors/<int:pk>/delete/', views.doctor_delete),

    # Patients
    path('patients/', views.patient_list),
    path('patients/create/', views.patient_create),
    path('patients/<int:pk>/', views.patient_detail),
    path('patients/<int:pk>/update/', views.patient_update),
    path('patients/<int:pk>/delete/', views.patient_delete),

    # Medical File
    path('patients/<int:patient_id>/medical-file/', views.medical_file_detail),
    path('patients/<int:patient_id>/medical-file/update/', views.medical_file_update),
    path('patients/<int:patient_id>/medical-file/delete/', views.medical_file_delete),
    path('patients/<int:patient_id>/medical-file/toggle-sharing/', views.toggle_medical_file_sharing),

    # Guardian
    path('patients/<int:patient_id>/guardian-file/', views.guardian_medical_file),
    path('guardian/my-children/', views.guardian_children),

    # Announcements
    path('announcements/', views.announcement_list),
    path('announcements/create/', views.announcement_create),
    path('announcements/<int:pk>/update/', views.announcement_update),
    path('announcements/<int:pk>/delete/', views.announcement_delete),

    # Schedules
    path('schedules/', views.schedule_list),
    path('schedules/create/', views.schedule_create),
    path('schedules/my-schedule/', views.my_schedule),
    path('schedules/<int:pk>/', views.schedule_detail),
    path('schedules/<int:pk>/update/', views.schedule_update),
    path('schedules/<int:pk>/delete/', views.schedule_delete),

    # Documents
    path('patients/<int:patient_id>/documents/', views.document_list),
    path('patients/<int:patient_id>/documents/create/', views.document_create),
    path('patients/<int:patient_id>/documents/<int:document_id>/update/', views.document_update),
    path('patients/<int:patient_id>/documents/<int:document_id>/delete/', views.document_delete),
    path('patients/<int:patient_id>/documents/<int:document_id>/toggle-visibility/', views.document_toggle_visibility),
    path('patients/<int:patient_id>/guardian-documents/', views.guardian_document_list),

    # Appointments
    path('appointments/', views.appointment_list),
    path('appointments/create/', views.appointment_create),
    path('appointments/<int:pk>/', views.appointment_detail),
    path('appointments/<int:pk>/update/', views.appointment_update),
    path('appointments/<int:pk>/delete/', views.appointment_delete),
    path('appointments/<int:pk>/status/', views.appointment_status_update),


    # Vaccinations
    path('patients/<int:patient_id>/vaccinations/', views.vaccination_list),
    path('patients/<int:patient_id>/vaccinations/create/', views.vaccination_create),
    path('patients/<int:patient_id>/vaccinations/<int:record_id>/', views.vaccination_detail),
    path('patients/<int:patient_id>/vaccinations/<int:record_id>/update/', views.vaccination_update),
    path('patients/<int:patient_id>/vaccinations/<int:record_id>/delete/', views.vaccination_delete),
    path('patients/<int:patient_id>/vaccinations/upcoming/', views.vaccination_upcoming),
]
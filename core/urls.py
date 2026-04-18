from django.urls import path
from . import views

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

    # Medical File
    path('patients/<int:patient_id>/medical-file/', views.medical_file_detail),
    path('patients/<int:patient_id>/medical-file/update/', views.medical_file_update),
    path('patients/<int:patient_id>/medical-file/delete/', views.medical_file_delete),
    path('patients/<int:patient_id>/medical-file/toggle-sharing/', views.toggle_medical_file_sharing),

    # Guardian
    path('patients/<int:patient_id>/guardian-file/', views.guardian_medical_file),
    path('guardian/my-children/', views.guardian_children),
]
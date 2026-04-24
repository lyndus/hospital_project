from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from django.db.models import Max
from datetime import date, timedelta
import re
from .models import *
from .serializers import *
from .permissions import IsAdmin, IsDoctor, IsGuardian, IsAdminOrDoctor


# ========================
# LOGIN
# ========================
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('email')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'role': user.role,
            'full_name': f"{user.first_name} {user.last_name}"
        })
    return Response({'error': 'Wrong username or password'}, status=400)


# ========================
# SERVICES
# ========================
@api_view(['GET'])
@permission_classes([IsAdminOrDoctor])
def service_list(request):
    services = Service.objects.all()
    return Response(ServiceSerializer(services, many=True).data)


@api_view(['POST'])
@permission_classes([IsAdmin])
def service_create(request):
    serializer = ServiceSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET'])
@permission_classes([IsAdminOrDoctor])
def service_detail(request, pk):
    try:
        service = Service.objects.get(pk=pk)
    except Service.DoesNotExist:
        return Response({'error': 'Service not found'}, status=404)
    return Response(ServiceSerializer(service).data)


@api_view(['PUT'])
@permission_classes([IsAdmin])
def service_update(request, pk):
    try:
        service = Service.objects.get(pk=pk)
    except Service.DoesNotExist:
        return Response({'error': 'Service not found'}, status=404)
    serializer = ServiceSerializer(service, data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAdmin])
def service_delete(request, pk):
    try:
        service = Service.objects.get(pk=pk)
    except Service.DoesNotExist:
        return Response({'error': 'Service not found'}, status=404)
    try:
        service.delete()
        return Response({'message': 'Service deleted'}, status=204)
    except Exception as e:
        return Response({
            'error': 'Cannot delete this service because it has doctors or appointments linked to it. Remove them first.'
        }, status=400)


# ========================
# DOCTORS
# ========================
@api_view(['GET'])
@permission_classes([IsAdminOrDoctor])
def doctor_list(request):
    doctors = Doctor.objects.all()
    return Response(DoctorSerializer(doctors, many=True).data)


@api_view(['POST'])
@permission_classes([IsAdmin])
def doctor_create(request):
    try:
        # Validate password first
        password = request.data.get('password')
        if not password or len(password) < 8:
            return Response({'error': 'Password must be at least 8 characters'}, status=400)

        # Validate email
        email = request.data.get('email')
        if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return Response({'error': 'Enter a valid email address'}, status=400)

        # Validate phone
        phone = request.data.get('phone')
        if phone:
            cleaned = re.sub(r'[\s\-]', '', phone)
            if not cleaned.isdigit() or not (7 <= len(cleaned) <= 15):
                return Response({'error': 'Phone must be digits only, between 7 and 15 numbers'}, status=400)

        user = User.objects.create_user(
            username=email,
            password=password,
            first_name=request.data.get('first_name'),
            last_name=request.data.get('last_name'),
            email=email,
            phone=phone,
            role='doctor'
        )
        doctor = Doctor.objects.create(
            user=user,
            service_id=request.data.get('service'),
            grade=request.data.get('grade')
        )
        return Response(DoctorSerializer(doctor).data, status=201)
    except Exception as e:
        return Response({'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAdminOrDoctor])
def doctor_detail(request, pk):
    try:
        doctor = Doctor.objects.get(pk=pk)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    return Response(DoctorSerializer(doctor).data)


@api_view(['PUT'])
@permission_classes([IsAdmin])
def doctor_update(request, pk):
    try:
        doctor = Doctor.objects.get(pk=pk)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    serializer = DoctorSerializer(doctor, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAdmin])
def doctor_delete(request, pk):
    try:
        doctor = Doctor.objects.get(pk=pk)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)
    try:
        doctor.user.delete()
        return Response({'message': 'Doctor deleted'}, status=204)
    except Exception as e:
        return Response({
            'error': 'Cannot delete this doctor because he has patients or records linked to him. Reassign them first.'
        }, status=400)


# ========================
# PATIENTS + GUARDIAN
# ========================
@api_view(['GET'])
@permission_classes([IsDoctor])
def patient_list(request):
    patients = Patient.objects.all()
    return Response(PatientSerializer(patients, many=True).data)


@api_view(['POST'])
@permission_classes([IsDoctor])
def patient_create(request):
    try:
        phone = request.data.get('guardian_phone')

        if not phone:
            return Response({'error': 'Guardian phone is required'}, status=400)

        # Validate phone format
        cleaned = re.sub(r'[\s\-]', '', phone)
        if not cleaned.isdigit() or not (7 <= len(cleaned) <= 15):
            return Response({'error': 'Guardian phone must be digits only, between 7 and 15 numbers'}, status=400)

        try:
            guardian = User.objects.get(phone=phone, role='guardian')
        except User.DoesNotExist:
            email = request.data.get('guardian_email')
            if not email:
                return Response({'error': 'Guardian email is required for new guardian'}, status=400)

            # Validate email format
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return Response({'error': 'Guardian email is not valid'}, status=400)

            guardian = User.objects.create_user(
                username=email,
                password='Change@123',
                first_name=request.data.get('guardian_first_name', ''),
                last_name=request.data.get('guardian_last_name', ''),
                phone=phone,
                email=email,
                role='guardian'
            )

        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor profile not found'}, status=404)

        height = request.data.get('height')
        weight = request.data.get('weight')
        blood_type = request.data.get('blood_type')

        if not height or not weight or not blood_type:
            return Response({
                'error': 'height, weight and blood_type are required'
            }, status=400)

        with transaction.atomic():
            patient = Patient.objects.create(
                guardian=guardian,
                created_by=doctor,
                patient_first_name=request.data.get('patient_first_name'),
                patient_last_name=request.data.get('patient_last_name'),
                patient_date_of_birth=request.data.get('patient_date_of_birth'),
                gender=request.data.get('gender'),
            )

            MedicalFile.objects.create(
                patient=patient,
                height=height,
                weight=weight,
                blood_type=blood_type,
                allergies=request.data.get('allergies', ''),
                chronic_condition=request.data.get('chronic_condition', '')
            )

        return Response({
            'message': 'Patient and medical file created successfully',
            'patient': PatientSerializer(patient).data,
        }, status=201)

    except Exception as e:
        return Response({'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsDoctor])
def patient_detail(request, pk):
    try:
        patient = Patient.objects.get(pk=pk)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    return Response(PatientSerializer(patient).data)


@api_view(['PUT'])
@permission_classes([IsDoctor])
def patient_update(request, pk):
    try:
        patient = Patient.objects.get(pk=pk)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    serializer = PatientSerializer(patient, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAdmin])
def patient_delete(request, pk):
    try:
        patient = Patient.objects.get(pk=pk)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    patient.delete()
    return Response({'message': 'Patient and all related data deleted'}, status=204)


# ========================
# MEDICAL FILE
# ========================
@api_view(['GET'])
@permission_classes([IsDoctor])
def medical_file_detail(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        medical_file = MedicalFile.objects.get(patient=patient)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)

    try:
        requesting_doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=404)

    is_creator = patient.created_by == requesting_doctor
    is_shared = medical_file.is_shared

    if not is_creator and not is_shared:
        return Response({
            'message': 'This patient exists but the guardian has not shared the medical file',
            'patient_name': f"{patient.patient_first_name} {patient.patient_last_name}",
        }, status=403)

    data = MedicalFileSerializer(medical_file).data
    data['patient_info'] = {
        'full_name': f"{patient.patient_first_name} {patient.patient_last_name}",
        'date_of_birth': patient.patient_date_of_birth,
        'gender': patient.gender,
        'created_by': f"Dr. {patient.created_by.user.first_name} {patient.created_by.user.last_name}",
        'service': patient.created_by.service.name,
    }
    data['last_edited_by'] = f"Dr. {medical_file.last_edited_by.user.first_name} {medical_file.last_edited_by.user.last_name}" if medical_file.last_edited_by else None
    data['last_edited_at'] = medical_file.last_edited_at
    return Response(data)


@api_view(['PUT'])
@permission_classes([IsDoctor])
def medical_file_update(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        medical_file = MedicalFile.objects.get(patient=patient)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)

    try:
        requesting_doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=404)

    is_creator = patient.created_by == requesting_doctor
    is_shared = medical_file.is_shared

    if not is_creator and not is_shared:
        return Response({
            'message': 'Access denied — guardian has not shared this medical file',
        }, status=403)

    serializer = MedicalFileSerializer(medical_file, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save(
            last_edited_by=requesting_doctor,
            last_edited_at=timezone.now()
        )
        return Response({
            'message': 'Medical file updated successfully',
            'data': serializer.data
        })
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAdmin])
def medical_file_delete(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        medical_file = MedicalFile.objects.get(patient=patient)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)
    medical_file.delete()
    return Response({'message': 'Medical file deleted'}, status=204)


@api_view(['GET'])
@permission_classes([IsGuardian])
def guardian_medical_file(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id, guardian=request.user)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found or access denied'}, status=404)

    medical_file = MedicalFile.objects.get(patient=patient)
    visible_documents = Document.objects.filter(file=medical_file, is_visible=True)

    data = MedicalFileSerializer(medical_file).data
    data['patient_info'] = {
        'full_name': f"{patient.patient_first_name} {patient.patient_last_name}",
        'date_of_birth': patient.patient_date_of_birth,
        'gender': patient.gender,
    }
    data['visible_documents'] = DocumentSerializer(visible_documents, many=True).data
    return Response(data)


@api_view(['GET'])
@permission_classes([IsGuardian])
def guardian_children(request):
    patients = Patient.objects.filter(guardian=request.user)
    data = []
    for patient in patients:
        data.append({
            'id': patient.id,
            'full_name': f"{patient.patient_first_name} {patient.patient_last_name}",
            'date_of_birth': patient.patient_date_of_birth,
            'gender': patient.gender,
        })
    return Response(data)


@api_view(['PATCH'])
@permission_classes([IsGuardian])
def toggle_medical_file_sharing(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id, guardian=request.user)
        medical_file = MedicalFile.objects.get(patient=patient)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found or access denied'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)

    medical_file.is_shared = not medical_file.is_shared
    medical_file.save()
    return Response({
        'message': f"Medical file is now {'shared with all doctors' if medical_file.is_shared else 'private — only creator doctor can access'}",
        'is_shared': medical_file.is_shared
    })


# ========================
# DOCUMENTS
# ========================
@api_view(['GET'])
@permission_classes([IsDoctor])
def document_list(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        medical_file = MedicalFile.objects.get(patient=patient)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)

    try:
        requesting_doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=404)

    is_creator = patient.created_by == requesting_doctor
    is_shared = medical_file.is_shared

    if not is_creator and not is_shared:
        return Response({'error': 'Access denied'}, status=403)

    documents = Document.objects.filter(file=medical_file)
    return Response(DocumentSerializer(documents, many=True).data)


@api_view(['POST'])
@permission_classes([IsDoctor])
def document_create(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        medical_file = MedicalFile.objects.get(patient=patient)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)

    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=404)

    is_creator = patient.created_by == doctor
    is_shared = medical_file.is_shared

    if not is_creator and not is_shared:
        return Response({'error': 'Access denied'}, status=403)

    serializer = DocumentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(
            file=medical_file,
            uploaded_by=doctor,
            service=doctor.service
        )
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PUT'])
@permission_classes([IsDoctor])
def document_update(request, patient_id, document_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        medical_file = MedicalFile.objects.get(patient=patient)
        document = Document.objects.get(pk=document_id, file=medical_file)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)
    except Document.DoesNotExist:
        return Response({'error': 'Document not found'}, status=404)

    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=404)

    is_creator = patient.created_by == doctor
    is_shared = medical_file.is_shared

    if not is_creator and not is_shared:
        return Response({'error': 'Access denied'}, status=403)

    serializer = DocumentSerializer(document, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsDoctor])
def document_delete(request, patient_id, document_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        medical_file = MedicalFile.objects.get(patient=patient)
        document = Document.objects.get(pk=document_id, file=medical_file)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)
    except Document.DoesNotExist:
        return Response({'error': 'Document not found'}, status=404)

    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=404)

    is_creator = patient.created_by == doctor
    is_shared = medical_file.is_shared

    if not is_creator and not is_shared:
        return Response({'error': 'Access denied'}, status=403)

    document.delete()
    return Response({'message': 'Document deleted'}, status=204)


@api_view(['PATCH'])
@permission_classes([IsDoctor])
def document_toggle_visibility(request, patient_id, document_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        medical_file = MedicalFile.objects.get(patient=patient)
        document = Document.objects.get(pk=document_id, file=medical_file)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)
    except Document.DoesNotExist:
        return Response({'error': 'Document not found'}, status=404)

    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=404)

    is_creator = patient.created_by == doctor
    is_shared = medical_file.is_shared

    if not is_creator and not is_shared:
        return Response({'error': 'Access denied'}, status=403)

    document.is_visible = not document.is_visible
    document.save()
    return Response({
        'message': f"Document is now {'visible' if document.is_visible else 'hidden'} to guardian",
        'is_visible': document.is_visible
    })


@api_view(['GET'])
@permission_classes([IsGuardian])
def guardian_document_list(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id, guardian=request.user)
        medical_file = MedicalFile.objects.get(patient=patient)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found or access denied'}, status=404)
    except MedicalFile.DoesNotExist:
        return Response({'error': 'Medical file not found'}, status=404)

    documents = Document.objects.filter(file=medical_file, is_visible=True)
    return Response(DocumentSerializer(documents, many=True).data)


@api_view(['GET'])
@permission_classes([IsDoctor])
def patient_search(request):
    query = request.query_params.get('q', '')
    if not query:
        return Response({'error': 'Please provide a search query'}, status=400)
    
    patients = Patient.objects.filter(
        Q(patient_first_name__icontains=query) |
        Q(patient_last_name__icontains=query)
    )
    return Response(PatientSerializer(patients, many=True).data)

# ========================
# ANNOUNCEMENTS
# ========================
@api_view(['POST'])
@permission_classes([IsAdmin])
def announcement_create(request):
    serializer = AnnouncementSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(posted_by=request.user)
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET'])
@permission_classes([AllowAny])
def announcement_list(request):
    user = request.user
    role = user.role if user.is_authenticated else "guest"

    announcements = Announcement.objects.filter(
        is_active=True
    ).filter(
        Q(target_audience="all") | Q(target_audience=role)
    ).order_by('-published_at')

    return Response(AnnouncementSerializer(announcements, many=True).data)


@api_view(['PUT'])
@permission_classes([IsAdmin])
def announcement_update(request, pk):
    try:
        announcement = Announcement.objects.get(pk=pk)
    except Announcement.DoesNotExist:
        return Response({'error': 'Announcement not found'}, status=404)

    serializer = AnnouncementSerializer(announcement, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAdmin])
def announcement_delete(request, pk):
    try:
        announcement = Announcement.objects.get(pk=pk)
    except Announcement.DoesNotExist:
        return Response({'error': 'Announcement not found'}, status=404)
    announcement.delete()
    return Response({'message': 'Announcement deleted'}, status=204)


# ========================
# SCHEDULE
# ========================
@api_view(['POST'])
@permission_classes([IsAdmin])
def schedule_create(request):
    serializer = ScheduleSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    doctor = serializer.validated_data['doctor']
    day = serializer.validated_data['day_of_week']
    start = serializer.validated_data['start_time']
    end = serializer.validated_data['end_time']

    if start >= end:
        return Response({'error': 'Start time must be before end time'}, status=400)

    conflict = Schedule.objects.filter(
        doctor__service=doctor.service,
        day_of_week=day
    ).filter(
        Q(start_time__lt=end) & Q(end_time__gt=start)
    ).exists()

    if conflict:
        return Response({
            'error': 'Doctors from the same service cannot overlap in schedule'
        }, status=400)

    schedule = serializer.save()
    return Response({
        'message': 'Schedule created successfully',
        'data': ScheduleSerializer(schedule).data
    }, status=201)


@api_view(['GET'])
@permission_classes([AllowAny])
def schedule_list(request):
    user = request.user

    if user.is_authenticated and user.role == 'admin':
        schedules = Schedule.objects.all()
    elif user.is_authenticated and user.role == 'doctor':
        try:
            doctor = Doctor.objects.get(user=user)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor profile not found'}, status=404)
        schedules = Schedule.objects.filter(doctor=doctor)
    else:
        schedules = Schedule.objects.all()

    return Response(ScheduleSerializer(schedules, many=True).data)


@api_view(['GET'])
@permission_classes([IsDoctor])
def my_schedule(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=404)
    schedules = Schedule.objects.filter(doctor=doctor)
    return Response(ScheduleSerializer(schedules, many=True).data)


@api_view(['GET'])
@permission_classes([IsAdmin])
def schedule_detail(request, pk):
    try:
        schedule = Schedule.objects.get(pk=pk)
    except Schedule.DoesNotExist:
        return Response({'error': 'Schedule not found'}, status=404)
    return Response(ScheduleSerializer(schedule).data)


@api_view(['PUT'])
@permission_classes([IsAdmin])
def schedule_update(request, pk):
    try:
        schedule = Schedule.objects.get(pk=pk)
    except Schedule.DoesNotExist:
        return Response({'error': 'Schedule not found'}, status=404)

    serializer = ScheduleSerializer(schedule, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    doctor = serializer.validated_data.get('doctor', schedule.doctor)
    day = serializer.validated_data.get('day_of_week', schedule.day_of_week)
    start = serializer.validated_data.get('start_time', schedule.start_time)
    end = serializer.validated_data.get('end_time', schedule.end_time)

    if start >= end:
        return Response({'error': 'Start time must be before end time'}, status=400)

    conflict = Schedule.objects.filter(
        doctor__service=doctor.service,
        day_of_week=day
    ).filter(
        Q(start_time__lt=end) & Q(end_time__gt=start)
    ).exclude(pk=pk).exists()

    if conflict:
        return Response({
            'error': 'Doctors from the same service cannot overlap in schedule'
        }, status=400)

    serializer.save()
    return Response({
        'message': 'Schedule updated successfully',
        'data': serializer.data
    })


@api_view(['DELETE'])
@permission_classes([IsAdmin])
def schedule_delete(request, pk):
    try:
        schedule = Schedule.objects.get(pk=pk)
    except Schedule.DoesNotExist:
        return Response({'error': 'Schedule not found'}, status=404)
    schedule.delete()
    return Response({'message': 'Schedule deleted'}, status=204)


# ========================
# APPOINTMENTS
# ========================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_list(request):
    user = request.user

    if user.role == 'admin':
        appointments = Appointment.objects.all()
    elif user.role == 'doctor':
        try:
            doctor = Doctor.objects.get(user=user)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor profile not found'}, status=404)
        appointments = Appointment.objects.filter(doctor=doctor)
    elif user.role == 'guardian':
        appointments = Appointment.objects.filter(patient__guardian=user)
    else:
        appointments = Appointment.objects.none()

    return Response(AppointmentSerializer(appointments, many=True).data)


@api_view(['POST'])
@permission_classes([AllowAny])
def appointment_create(request):
    try:
        doctor_id = request.data.get('doctor')
        appointment_date = request.data.get('appointment_date')

        if not doctor_id or not appointment_date:
            return Response({'error': 'doctor and appointment_date are required'}, status=400)

        try:
            doctor = Doctor.objects.get(pk=doctor_id)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=404)

        last = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date
        ).aggregate(Max('queue_number'))['queue_number__max']

        queue_number = (last or 0) + 1

        serializer = AppointmentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                queue_number=queue_number,
                service=doctor.service
            )
            return Response({
                'message': 'Appointment booked successfully',
                'queue_number': queue_number,
                'data': serializer.data
            }, status=201)
        return Response(serializer.errors, status=400)

    except Exception as e:
        return Response({'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_detail(request, pk):
    try:
        appointment = Appointment.objects.get(pk=pk)
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)
    return Response(AppointmentSerializer(appointment).data)


@api_view(['PUT'])
@permission_classes([IsAdminOrDoctor])
def appointment_update(request, pk):
    try:
        appointment = Appointment.objects.get(pk=pk)
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)

    serializer = AppointmentSerializer(appointment, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAdminOrDoctor])
def appointment_delete(request, pk):
    try:
        appointment = Appointment.objects.get(pk=pk)
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)
    appointment.delete()
    return Response({'message': 'Appointment deleted'}, status=204)


@api_view(['PATCH'])
@permission_classes([IsAdminOrDoctor])
def appointment_status_update(request, pk):
    try:
        appointment = Appointment.objects.get(pk=pk)
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)

    new_status = request.data.get('appointment_status')
    valid_statuses = ['pending', 'confirmed', 'completed', 'cancelled']

    if not new_status or new_status not in valid_statuses:
        return Response({
            'error': f"Status must be one of: {', '.join(valid_statuses)}"
        }, status=400)

    appointment.appointment_status = new_status
    appointment.save()
    return Response({
        'message': f"Appointment status updated to {new_status}",
        'appointment_status': new_status
    })


# ========================
# VACCINATION
# ========================
@api_view(['POST'])
@permission_classes([IsDoctor])
def vaccination_create(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor profile not found'}, status=404)

    serializer = VaccinationRecordSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(
            patient=patient,
            administered_by=doctor
        )
        return Response({
            'message': 'Vaccination record created successfully',
            'data': serializer.data
        }, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vaccination_list(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    user = request.user
    if user.role == 'guardian':
        if patient.guardian != user:
            return Response({'error': 'Access denied'}, status=403)

    records = VaccinationRecord.objects.filter(patient=patient)
    return Response(VaccinationRecordSerializer(records, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vaccination_detail(request, patient_id, record_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        record = VaccinationRecord.objects.get(pk=record_id, patient=patient)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except VaccinationRecord.DoesNotExist:
        return Response({'error': 'Record not found'}, status=404)

    user = request.user
    if user.role == 'guardian':
        if patient.guardian != user:
            return Response({'error': 'Access denied'}, status=403)

    return Response(VaccinationRecordSerializer(record).data)


@api_view(['PUT'])
@permission_classes([IsDoctor])
def vaccination_update(request, patient_id, record_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
        record = VaccinationRecord.objects.get(pk=record_id, patient=patient)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)
    except VaccinationRecord.DoesNotExist:
        return Response({'error': 'Record not found'}, status=404)

    serializer = VaccinationRecordSerializer(record, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Vaccination record updated successfully',
            'data': serializer.data
        })
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsDoctor])
def vaccination_delete(request, patient_id, record_id):
    return Response({
        'error': 'Vaccination records cannot be deleted. They are permanent medical history.'
    }, status=403)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vaccination_upcoming(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    user = request.user
    if user.role == 'guardian':
        if patient.guardian != user:
            return Response({'error': 'Access denied'}, status=403)

    today = date.today()
    next_month = today + timedelta(days=30)

    upcoming = VaccinationRecord.objects.filter(
        patient=patient,
        next_dose_date__range=(today, next_month)
    ).order_by('next_dose_date')

    return Response(VaccinationRecordSerializer(upcoming, many=True).data)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Max, Count
from datetime import date, timedelta, datetime
import re
import secrets
import string
from .models import *
from .serializers import *
from .permissions import IsAdmin, IsDoctor, IsGuardian, IsAdminOrDoctor


# ========================
# HELPERS
# ========================
def generate_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$"
    return ''.join(secrets.choice(chars) for _ in range(length))


# ========================
# AUTH
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'error': 'Refresh token is required'}, status=400)
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'message': 'Logged out successfully'})
    except TokenError:
        return Response({'error': 'Invalid or expired token'}, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh_view(request):
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'error': 'Refresh token is required'}, status=400)
    try:
        token = RefreshToken(refresh_token)
        return Response({
            'access': str(token.access_token)
        })
    except TokenError:
        return Response({'error': 'Invalid or expired token'}, status=400)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not old_password or not new_password:
        return Response({'error': 'old_password and new_password are required'}, status=400)

    if not user.check_password(old_password):
        return Response({'error': 'Old password is incorrect'}, status=400)

    if len(new_password) < 8:
        return Response({'error': 'New password must be at least 8 characters'}, status=400)

    if old_password == new_password:
        return Response({'error': 'New password must be different from old password'}, status=400)

    user.set_password(new_password)
    user.save()
    return Response({'message': 'Password changed successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_profile(request):
    user = request.user
    data = {
        'id': user.id,
        'full_name': f"{user.first_name} {user.last_name}",
        'email': user.email,
        'phone': user.phone,
        'address': user.address,
        'role': user.role,
    }
    if user.role == 'doctor':
        try:
            doctor = Doctor.objects.get(user=user)
            data['service'] = doctor.service.name
            data['grade'] = doctor.grade
        except Doctor.DoesNotExist:
            pass
    return Response(data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    allowed_fields = ['first_name', 'last_name', 'phone', 'address']

    # Doctors cannot update their own profile details (admin manages that)
    if user.role == 'doctor':
        return Response({'error': 'Doctors must contact admin to update their profile'}, status=403)

    for field in allowed_fields:
        value = request.data.get(field)
        if value:
            if field == 'phone':
                cleaned = re.sub(r'[\s\-]', '', value)
                if not cleaned.isdigit() or not (7 <= len(cleaned) <= 15):
                    return Response({'error': 'Phone must be digits only, between 7 and 15 numbers'}, status=400)
            setattr(user, field, value)

    user.save()
    return Response({
        'message': 'Profile updated successfully',
        'data': {
            'full_name': f"{user.first_name} {user.last_name}",
            'phone': user.phone,
            'address': user.address,
        }
    })


# ========================
# SERVICES
# ========================
@api_view(['GET'])
@permission_classes([AllowAny])
def service_list_public(request):
    services = Service.objects.all()
    return Response([{'id': s.id, 'name': s.name} for s in services])


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
    doctors = Doctor.objects.select_related('user', 'service').all()
    return Response([
        {
            'id': d.id,
            'first_name': d.user.first_name,
            'last_name': d.user.last_name,
            'full_name': f"Dr. {d.user.first_name} {d.user.last_name}",
            'email': d.user.email,
            'phone': d.user.phone,
            'service': d.service.name,
            'service_id': d.service.id,
            'grade': d.grade,
        }
        for d in doctors
    ])

@api_view(['GET'])
@permission_classes([AllowAny])
def doctor_list_public(request):
    doctors = Doctor.objects.select_related('user', 'service').all()
    return Response([
        {
            'id': d.id,
            'full_name': f"Dr. {d.user.first_name} {d.user.last_name}",
            'service': d.service.name,
            'grade': d.grade,
        }
        for d in doctors
    ])

@api_view(['POST'])
@permission_classes([IsAdmin])
def doctor_create(request):
    try:
        password = request.data.get('password')
        if not password or len(password) < 8:
            return Response({'error': 'Password must be at least 8 characters'}, status=400)

        email = request.data.get('email')
        if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return Response({'error': 'Enter a valid email address'}, status=400)

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


@api_view(['POST'])
@permission_classes([IsDoctor])
def patient_create(request):
    try:
        phone = request.data.get('guardian_phone')
        if not phone:
            return Response({'error': 'Guardian phone is required'}, status=400)

        cleaned = re.sub(r'[\s\-]', '', phone)
        if not cleaned.isdigit() or not (7 <= len(cleaned) <= 15):
            return Response({'error': 'Guardian phone must be digits only, between 7 and 15 numbers'}, status=400)

        try:
            guardian = User.objects.get(phone=phone, role='guardian')
            temp_password = None
        except User.DoesNotExist:
            email = request.data.get('guardian_email')
            if not email:
                return Response({'error': 'Guardian email is required for new guardian'}, status=400)
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return Response({'error': 'Guardian email is not valid'}, status=400)

            temp_password = generate_password()
            guardian = User.objects.create_user(
                username=email,
                password=temp_password,
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
            return Response({'error': 'height, weight and blood_type are required'}, status=400)

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
            AuditLog.objects.create(
               performed_by=request.user,
               action="created",
               model_name="Patient",
               record_id=patient.id,
               notes=f"Patient {patient.patient_first_name} {patient.patient_last_name} created"
            )

        response_data = {
            'message': 'Patient and medical file created successfully',
            'patient': PatientSerializer(patient).data,
        }
        if temp_password:
            response_data['guardian_temp_password'] = temp_password

        return Response(response_data, status=201)

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
    AuditLog.objects.create(
        performed_by=request.user,
        action="deleted",
        model_name="Patient",
        record_id=patient.id,
        notes=f"Patient {patient.patient_first_name} {patient.patient_last_name} deleted"
    )
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

    data = MedicalFileSerializer(medical_file).data
    data['patient_info'] = {
        'full_name': f"{patient.patient_first_name} {patient.patient_last_name}",
        'date_of_birth': patient.patient_date_of_birth,
        'gender': patient.gender,
        'created_by': f"Dr. {patient.created_by.user.first_name} {patient.created_by.user.last_name}",
        'service': patient.created_by.service.name,
    }
    data['last_edited_by'] = (
        f"Dr. {medical_file.last_edited_by.user.first_name} {medical_file.last_edited_by.user.last_name}"
        if medical_file.last_edited_by else None
    )
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

    serializer = MedicalFileSerializer(medical_file, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save(last_edited_by=requesting_doctor, last_edited_at=timezone.now())
        AuditLog.objects.create(
            performed_by=request.user,
            action="updated",
            model_name="MedicalFile",
            record_id=medical_file.id,
            notes=f"Medical file of patient #{patient_id} updated"
        )
        return Response({'message': 'Medical file updated successfully', 'data': serializer.data})
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

    # Optional filter by document type
    doc_type = request.query_params.get('type', None)
    documents = Document.objects.filter(file=medical_file)
    if doc_type:
        documents = documents.filter(document_type=doc_type)

    return Response(DocumentSerializer(documents, many=True).data)


@api_view(['GET'])
@permission_classes([IsDoctor])
def document_detail(request, patient_id, document_id):
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
    return Response(DocumentSerializer(document).data)


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

    serializer = DocumentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(file=medical_file, uploaded_by=doctor, service=doctor.service)
        AuditLog.objects.create(
            performed_by=request.user,
            action="created",
            model_name="Document",
            record_id=serializer.instance.id,
            notes=f"Document '{serializer.instance.file_name}' uploaded for patient #{patient_id}"
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
    AuditLog.objects.create(
        performed_by=request.user,
        action="deleted",
        model_name="Document",
        record_id=document.id,
        notes=f"Document '{document.file_name}' deleted for patient #{patient_id}"
    )
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

    document.is_visible = not document.is_visible
    document.save()
    AuditLog.objects.create(
        performed_by=request.user,
        action="visibility_toggled",
        model_name="Document",
        record_id=document.id,
        notes=f"Document '{document.file_name}' visibility set to {document.is_visible} for patient #{patient_id}"
    )
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

    if user.is_authenticated and user.role == 'admin':
        announcements = Announcement.objects.filter(is_active=True).order_by('-published_at')
    else:
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

    start = serializer.validated_data['start_time']
    end = serializer.validated_data['end_time']

    if start >= end:
        return Response({'error': 'Start time must be before end time'}, status=400)

    schedule = serializer.save()
    return Response({
        'message': 'Schedule created successfully',
        'data': ScheduleSerializer(schedule).data
    }, status=201)


@api_view(['GET'])
@permission_classes([AllowAny])
def schedule_list(request):
    user = request.user
    if user.is_authenticated and user.role == 'doctor':
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

    start = serializer.validated_data.get('start_time', schedule.start_time)
    end = serializer.validated_data.get('end_time', schedule.end_time)

    if start >= end:
        return Response({'error': 'Start time must be before end time'}, status=400)

    serializer.save()
    return Response({'message': 'Schedule updated successfully', 'data': serializer.data})


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
        doctor_name = request.data.get('doctor_name')
        appointment_date = request.data.get('appointment_date')

        if not doctor_name or not appointment_date:
            return Response({'error': 'doctor_name and appointment_date are required'}, status=400)

        try:
            appointment_date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        if appointment_date_obj < date.today():
            return Response({'error': 'Appointment date cannot be in the past'}, status=400)

        name_parts = doctor_name.strip().split()
        if len(name_parts) < 2:
            return Response({'error': 'Please enter both first and last name of the doctor'}, status=400)

        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:])

        try:
            doctor = Doctor.objects.get(
                user__first_name__iexact=first_name,
                user__last_name__iexact=last_name
            )
        except Doctor.DoesNotExist:
            return Response({'error': 'No doctor found with that name'}, status=404)
        except Doctor.MultipleObjectsReturned:
            return Response({'error': 'Multiple doctors found with that name, please contact the clinic'}, status=400)

        day_name = appointment_date_obj.strftime('%A').lower()
        schedule = Schedule.objects.filter(
            doctor=doctor,
            day_of_week__iexact=day_name
        ).first()

        if not schedule:
            return Response({
                'error': f"Dr. {doctor.user.first_name} {doctor.user.last_name} does not work on {day_name.capitalize()}"
            }, status=400)

        current_count = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_status__in=['pending', 'confirmed']
        ).count()

        if current_count >= schedule.max_appointments:
            return Response({
                'error': f"Dr. {doctor.user.first_name} {doctor.user.last_name} is fully booked on {day_name.capitalize()}"
            }, status=400)

        patient_id = request.data.get('patient_id')
        guest_first = request.data.get('guest_first_name', '').strip()
        guest_last = request.data.get('guest_last_name', '').strip()
        guest_phone = request.data.get('guest_phone', '').strip()
        cleaned_phone = None  # initialize here so it's accessible later

        if not patient_id:
            if not guest_first or not guest_last or not guest_phone:
                return Response({
                    'error': 'guest_first_name, guest_last_name, and guest_phone are required when no patient is linked'
                }, status=400)

            # Clean and validate Algerian phone number
            cleaned_phone = re.sub(r'[\s\-]', '', guest_phone)
            if not re.match(r'^0[567]\d{8}$', cleaned_phone):
                return Response({
                    'error': 'Phone number must start with 05, 06, or 07 and be exactly 10 digits'
                }, status=400)

            already_booked = Appointment.objects.filter(
                appointment_date=appointment_date,
                guest_phone=cleaned_phone,
                service=doctor.service,
                appointment_status__in=['pending', 'confirmed']
            ).exists()

            if already_booked:
                return Response({
                    'error': 'This phone number already has an active appointment in this service on that date'
                }, status=400)

        patient = None
        if patient_id:
            try:
                patient = Patient.objects.get(pk=patient_id)
            except Patient.DoesNotExist:
                return Response({'error': 'Patient not found'}, status=404)

            already_booked = Appointment.objects.filter(
                patient=patient,
                service=doctor.service,
                appointment_date=appointment_date,
                appointment_status__in=['pending', 'confirmed']
            ).exists()

            if already_booked:
                return Response({
                    'error': 'This patient already has an active appointment in this service on that date'
                }, status=400)

        last = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date
        ).aggregate(Max('queue_number'))['queue_number__max']

        queue_number = (last or 0) + 1

        # Merge cleaned phone into request data before passing to serializer
        data = request.data.copy()
        if cleaned_phone:
            data['guest_phone'] = cleaned_phone

        serializer = AppointmentSerializer(data=data)
        if serializer.is_valid():
            serializer.save(
                queue_number=queue_number,
                service=doctor.service,
                doctor=doctor,
                patient=patient
            )
            return Response({
                'message': 'Appointment booked successfully',
                'doctor': f"Dr. {doctor.user.first_name} {doctor.user.last_name}",
                'service': doctor.service.name,
                'day': day_name.capitalize(),
                'working_hours': f"{schedule.start_time} - {schedule.end_time}",
                'queue_number': queue_number,
                'remaining_slots': schedule.max_appointments - current_count - 1,
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

    user = request.user
    if user.role == 'guardian':
        owns_via_patient = (appointment.patient is not None and appointment.patient.guardian == user)
        owns_via_phone = (appointment.guest_phone == user.phone)
        if not owns_via_patient and not owns_via_phone:
            return Response({'error': 'Access denied'}, status=403)

    return Response(AppointmentSerializer(appointment).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_history(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    user = request.user
    if user.role == 'guardian' and patient.guardian != user:
        return Response({'error': 'Access denied'}, status=403)

    appointments = Appointment.objects.filter(
        patient=patient,
        appointment_status__in=['completed', 'cancelled']
    ).order_by('-appointment_date')

    return Response(AppointmentSerializer(appointments, many=True).data)


@api_view(['PATCH'])
@permission_classes([IsGuardian])
def appointment_cancel_guardian(request, pk):
    try:
        appointment = Appointment.objects.get(pk=pk)
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)

    # Guardian can only cancel their own child's appointment
    if appointment.patient is None or appointment.patient.guardian != request.user:
        return Response({'error': 'Access denied'}, status=403)

    if appointment.appointment_status in ['completed', 'cancelled']:
        return Response({'error': f"Cannot cancel an appointment that is already {appointment.appointment_status}"}, status=400)

    appointment.appointment_status = 'cancelled'
    appointment.save()
    return Response({'message': 'Appointment cancelled successfully', 'appointment_status': 'cancelled'})


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
        return Response({'error': f"Status must be one of: {', '.join(valid_statuses)}"}, status=400)

    appointment.appointment_status = new_status
    appointment.save()
    return Response({'message': f"Appointment status updated to {new_status}", 'appointment_status': new_status})


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
        serializer.save(patient=patient, administered_by=doctor)
        return Response({'message': 'Vaccination record created successfully', 'data': serializer.data}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vaccination_list(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    user = request.user
    if user.role == 'guardian' and patient.guardian != user:
        return Response({'error': 'Access denied'}, status=403)

    # Optional filter by status
    status_filter = request.query_params.get('status', None)
    records = VaccinationRecord.objects.filter(patient=patient)
    if status_filter in ['administered', 'scheduled']:
        records = records.filter(status=status_filter)

    # Optional search by vaccine name
    vaccine_name = request.query_params.get('vaccine', None)
    if vaccine_name:
        records = records.filter(vaccine_name__icontains=vaccine_name)

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
    if user.role == 'guardian' and patient.guardian != user:
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
        return Response({'message': 'Vaccination record updated successfully', 'data': serializer.data})
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsDoctor])
def vaccination_delete(request, patient_id, record_id):
    return Response({'error': 'Vaccination records cannot be deleted. They are permanent medical history.'}, status=403)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vaccination_upcoming(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=404)

    user = request.user
    if user.role == 'guardian' and patient.guardian != user:
        return Response({'error': 'Access denied'}, status=403)

    today = date.today()
    next_month = today + timedelta(days=30)
    upcoming = VaccinationRecord.objects.filter(
        patient=patient,
        next_dose_date__range=(today, next_month)
    ).order_by('next_dose_date')
    return Response(VaccinationRecordSerializer(upcoming, many=True).data)


# ========================
# ADMIN DASHBOARD
# ========================
@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_dashboard(request):
    today = date.today()

    total_patients = Patient.objects.count()
    total_doctors = Doctor.objects.count()
    total_services = Service.objects.count()
    total_appointments_today = Appointment.objects.filter(appointment_date=today).count()
    pending_appointments_today = Appointment.objects.filter(
        appointment_date=today,
        appointment_status='pending'
    ).count()

    # Appointments per doctor (today)
    appointments_per_doctor = (
        Appointment.objects
        .filter(appointment_date=today)
        .values('doctor__user__first_name', 'doctor__user__last_name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Most booked service (all time)
    most_booked_service = (
        Appointment.objects
        .values('service__name')
        .annotate(count=Count('id'))
        .order_by('-count')
        .first()
    )

    return Response({
        'total_patients': total_patients,
        'total_doctors': total_doctors,
        'total_services': total_services,
        'appointments_today': total_appointments_today,
        'pending_today': pending_appointments_today,
        'appointments_per_doctor_today': [
            {
                'doctor': f"Dr. {a['doctor__user__first_name']} {a['doctor__user__last_name']}",
                'appointments': a['count']
            }
            for a in appointments_per_doctor
        ],
        'most_booked_service': most_booked_service['service__name'] if most_booked_service else None,
    })
# ========================
# DOCTOR AVAILABILITY & SLOTS
# ========================
@api_view(['GET'])
@permission_classes([AllowAny])
def doctor_availability(request, pk):
    try:
        doctor = Doctor.objects.get(pk=pk)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    schedules = Schedule.objects.filter(doctor=doctor)
    return Response({
        'doctor': f"Dr. {doctor.user.first_name} {doctor.user.last_name}",
        'service': doctor.service.name,
        'availability': [{
            'day': s.day_of_week,
            'start_time': s.start_time,
            'end_time': s.end_time,
            'max_appointments': s.max_appointments,
        } for s in schedules]
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def doctor_slots(request, pk):
    try:
        doctor = Doctor.objects.get(pk=pk)
    except Doctor.DoesNotExist:
        return Response({'error': 'Doctor not found'}, status=404)

    date_str = request.query_params.get('date')
    if not date_str:
        return Response({'error': 'date parameter is required'}, status=400)

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    day_name = date_obj.strftime('%A').lower()

    schedule = Schedule.objects.filter(
        doctor=doctor,
        day_of_week=day_name
    ).first()

    if not schedule:
        return Response({
            'available': False,
            'message': f"Dr. {doctor.user.first_name} {doctor.user.last_name} does not work on {day_name.capitalize()}"
        })

    booked = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=date_str,
        appointment_status__in=['pending', 'confirmed']
    ).count()

    remaining = schedule.max_appointments - booked

    return Response({
        'doctor': f"Dr. {doctor.user.first_name} {doctor.user.last_name}",
        'date': date_str,
        'day': day_name.capitalize(),
        'available': remaining > 0,
        'remaining_slots': remaining,
        'max_slots': schedule.max_appointments,
        'booked': booked,
    })


# ========================
# FILTERS
# ========================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_filter(request):
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

    # Filter by date
    date_filter = request.query_params.get('date')
    if date_filter:
        appointments = appointments.filter(appointment_date=date_filter)

    # Filter by status
    status_filter = request.query_params.get('status')
    if status_filter:
        appointments = appointments.filter(appointment_status=status_filter)

    return Response(AppointmentSerializer(appointments, many=True).data)


@api_view(['GET'])
@permission_classes([IsDoctor])
def patient_filter(request):
    # Filter by created_by=me
    created_by = request.query_params.get('created_by')
    if created_by == 'me':
        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor profile not found'}, status=404)
        patients = Patient.objects.filter(created_by=doctor)
    else:
        patients = Patient.objects.all()

    return Response(PatientSerializer(patients, many=True).data)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.utils import timezone
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
    service.delete()
    return Response({'message': 'Service deleted'}, status=204)


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
        user = User.objects.create_user(
            username=request.data.get('email'),
            password=request.data.get('password'),
            first_name=request.data.get('first_name'),
            last_name=request.data.get('last_name'),
            email=request.data.get('email'),
            phone=request.data.get('phone'),
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
    doctor.user.delete()
    return Response({'message': 'Doctor deleted'}, status=204)


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

        try:
            guardian = User.objects.get(phone=phone, role='guardian')
        except User.DoesNotExist:
            email = request.data.get('guardian_email')
            if not email:
                return Response({'error': 'Guardian email is required for new guardian'}, status=400)

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
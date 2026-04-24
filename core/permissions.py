from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'

class IsDoctor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'doctor'

class IsGuardian(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'guardian'

class IsAdminOrDoctor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'doctor']

class IsOwnerGuardian(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'guardian'

    def has_object_permission(self, request, view, obj):
        return obj.guardian == request.user
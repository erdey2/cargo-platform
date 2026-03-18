from .serializers import RegisterSerializer
from rest_framework import generics, permissions
from .serializers import ProfileSerializer
from ..models import Profile


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.profile

class ProfileListView(generics.ListAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAdminUser]

    queryset = Profile.objects.all()
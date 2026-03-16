from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import Assignment
from .serializers import (
    AssignmentSerializer,
    AssignmentStatusUpdateSerializer
)

from apps.assignment.services.assignment import AssignmentService

class AssignmentViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        user = self.request.user

        if user.is_staff:
            return Assignment.objects.all()

        return Assignment.objects.filter(
            driver__user=user
        )

class AssignmentStatusUpdateView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):

        assignment = Assignment.objects.get(id=assignment_id)

        serializer = AssignmentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]

        assignment = AssignmentService.change_status(
            assignment,
            new_status,
            request.user
        )

        return Response(
            AssignmentSerializer(assignment).data
        )
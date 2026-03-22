from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import Assignment
from .serializers import AssignmentSerializer, AssignmentStatusUpdateSerializer
from apps.assignment.services.assignment import AssignmentService
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter


@extend_schema(
    tags=["Assignments"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List assignments",
        description="Retrieve assignments. Admins see all assignments, drivers see only their assigned jobs.",
        responses={200: AssignmentSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Retrieve assignment",
        description="Get details of a specific assignment.",
        responses={200: AssignmentSerializer}
    ),
)
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

@extend_schema(
    tags=["Assignments"],
)
class AssignmentStatusUpdateView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Update assignment status",
        description=(
            "Update the status of an assignment.\n\n"
            "This will:\n"
            "- Validate the new status\n"
            "- Apply business rules via AssignmentService\n"
            "- Update assignment state (e.g., accepted, rejected, completed)"
        ),
        parameters=[
            OpenApiParameter(
                name="assignment_id",
                description="ID of the assignment",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            )
        ],
        request=AssignmentStatusUpdateSerializer,
        responses={200: AssignmentSerializer}
    )
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
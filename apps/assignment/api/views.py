from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from ..models import Assignment
from .serializers import AssignmentSerializer, AssignmentStatusUpdateSerializer
from apps.assignment.services.assignment import AssignmentService
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, OpenApiExample


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

@extend_schema(tags=["Assignments"])
class AssignmentStatusUpdateView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Update assignment status",
        description=(
            "Update the status of an assignment.\n\n"
            "Allowed values:\n"
            "- assigned\n"
            "- driver_arriving\n"
            "- in_transit\n"
            "- delivered\n"
            "- completed\n"
            "- cancelled\n\n"
            "Rules:\n"
            "- Only assigned driver or admin can update\n"
            "- Business logic is handled in AssignmentService"
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
        responses={
            200: AssignmentSerializer,
            400: OpenApiResponse(description="Invalid status"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Assignment not found"),
        },
        examples=[
            OpenApiExample(
                "Driver arriving",
                value={"status": "driver_arriving"},
                request_only=True,
            ),
            OpenApiExample(
                "Start delivery",
                value={"status": "in_transit"},
                request_only=True,
            ),
            OpenApiExample(
                "Complete delivery",
                value={"status": "completed"},
                request_only=True,
            ),
        ],
    )
    def post(self, request, assignment_id):

        try:
            assignment = Assignment.objects.select_related(
                "driver__user"
            ).get(id=assignment_id)
        except Assignment.DoesNotExist:
            raise NotFound("Assignment not found")

        is_owner_driver = assignment.driver.user_id == request.user.id

        if not (request.user.is_staff or request.user.is_superuser or is_owner_driver):
            raise PermissionDenied("Not allowed to update this assignment")

        serializer = AssignmentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]

        assignment = AssignmentService.change_status(
            assignment,
            new_status,
            request.user
        )

        return Response(AssignmentSerializer(assignment).data)
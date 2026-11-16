from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import Project
from .serializers import ProjectAdminSerializer, delete_stored_file

# The homepage carousel autoplays through everything it's given, so keep it to
# the most recent handful rather than the whole portfolio.
HOME_LIMIT = 12


# --- Public pages -------------------------------------------------------
# Called by config.views (the / and /projects/ pages) so each page keeps
# living where the rest of the site's pages do.

def published_projects():
    return list(Project.objects.published())


def homepage_projects():
    return list(Project.objects.on_home()[:HOME_LIMIT])


# --- Admin dashboard ----------------------------------------------------

@login_required(login_url='/admin-dashboard/login')
def admin_projects_page(request):
    return render(request, 'admin-dashboard/projects.html', {'active_nav': 'projects'})


class ProjectAdminViewSet(viewsets.ModelViewSet):
    """Full CRUD on projects for the dashboard, including image upload
    (multipart), the publish / homepage switches and manual ordering."""
    queryset = Project.objects.all()
    serializer_class = ProjectAdminSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    # The dashboard filters and searches client-side over the full list.
    pagination_class = None

    def perform_destroy(self, instance):
        image = instance.image
        name = image.name if image else None
        storage = image.storage if image else None

        instance.delete()
        delete_stored_file(storage, name)

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """Set the display order. Expects every project id, in the new order.

        Requiring the complete list (not just the ones that moved) means a
        stale page can't silently scramble a list someone else has changed
        since: it gets a 400 and is told to refresh.
        """
        ids = request.data.get('ids')

        if not isinstance(ids, list) or not all(isinstance(pk, int) and not isinstance(pk, bool) for pk in ids):
            return Response(
                {'detail': 'ids must be a list of project ids.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        projects = {project.pk: project for project in Project.objects.all()}

        if len(ids) != len(set(ids)) or set(ids) != set(projects):
            return Response(
                {'detail': 'The list is out of date. Refresh the page and try again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for position, pk in enumerate(ids, start=1):
                projects[pk].sort_order = position

            Project.objects.bulk_update(projects.values(), ['sort_order'])

        return Response(self.get_serializer(Project.objects.all(), many=True).data)

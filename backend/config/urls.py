from django.urls import path
from drf_spectacular.views import SpectacularAPIView
from app.core.api import SessionView, CoursesView, TasksView, TaskView, CancelView, RetryView
from app.materials.api import (MaterialsView, ClassificationView, RelationsView,
                               RemoveRelationView, SourceView, PageImageView, OriginalView)
from app.courses.api import (ProfileView, AnalysisPreflightView, AnalyseView, DraftView, AnswerView, ConfirmView, VersionView)

urlpatterns = [
    path("api/v1/session", SessionView.as_view()),
    path("api/v1/courses", CoursesView.as_view()),
    path("api/v1/courses/<uuid:course_id>/profile", ProfileView.as_view()),
    path("api/v1/courses/<uuid:course_id>/analysis-preflight", AnalysisPreflightView.as_view()),
    path("api/v1/courses/<uuid:course_id>/analyses", AnalyseView.as_view()),
    path("api/v1/courses/<uuid:course_id>/draft", DraftView.as_view()),
    path("api/v1/courses/<uuid:course_id>/answers", AnswerView.as_view()),
    path("api/v1/courses/<uuid:course_id>/confirmations", ConfirmView.as_view()),
    path("api/v1/courses/<uuid:course_id>/versions/<uuid:version_id>", VersionView.as_view()),
    path("api/v1/courses/<uuid:course_id>/materials", MaterialsView.as_view()),
    path("api/v1/courses/<uuid:course_id>/tasks", TasksView.as_view()),
    path("api/v1/material-versions/<uuid:version_id>/classification", ClassificationView.as_view()),
    path("api/v1/material-versions/<uuid:version_id>/relations", RelationsView.as_view()),
    path("api/v1/relations/<uuid:relation_id>/remove", RemoveRelationView.as_view()),
    path("api/v1/material-versions/<uuid:version_id>/pages/<int:page_number>", PageImageView.as_view()),
    path("api/v1/material-versions/<uuid:version_id>/original", OriginalView.as_view()),
    path("api/v1/sources/<uuid:evidence_id>", SourceView.as_view()),
    path("api/v1/tasks/<uuid:task_id>", TaskView.as_view()),
    path("api/v1/tasks/<uuid:task_id>/cancel", CancelView.as_view()),
    path("api/v1/tasks/<uuid:task_id>/retries", RetryView.as_view()),
    path("api/schema", SpectacularAPIView.as_view()),
]

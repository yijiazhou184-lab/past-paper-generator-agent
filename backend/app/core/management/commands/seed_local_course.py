from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from app.courses.models import Course


class Command(BaseCommand):
    help = "Create a controlled local test identity and the first QM workspace."

    def handle(self, *args, **options):
        owner, created = get_user_model().objects.get_or_create(username="local")
        if created:
            owner.set_unusable_password()
            owner.save()
        course, _ = Course.objects.get_or_create(owner=owner, code="MSIN0180",
            defaults={"title": "Quantitative Methods", "scope_statement": "All lecture content",
                      "scope_provenance": "user_statement"})
        self.stdout.write(f"Local course: {course.id}")

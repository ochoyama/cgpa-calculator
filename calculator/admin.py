from django.contrib import admin

from .models import Student
from .models import Semester
from .models import Course
from .models import ContactMessage


admin.site.register(Student)
admin.site.register(Semester)
admin.site.register(Course)

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "email",
        "subject",
        "created_at",
        "is_read",
    )

    list_filter = (
        "is_read",
        "created_at",
    )

    search_fields = (
        "name",
        "email",
        "subject",
        "message",
    )

    ordering = (
        "-created_at",
    )
from django.contrib import admin

from .models import Student
from .models import Semester
from .models import Course


admin.site.register(Student)
admin.site.register(Semester)
admin.site.register(Course)
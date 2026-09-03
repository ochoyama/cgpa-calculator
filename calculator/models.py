
from django.db import models
from django.contrib.auth.models import User


# =========================================================
# STUDENT MODEL
# =========================================================

class Student(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    name = models.CharField(
        max_length=200
    )

    matric_number = models.CharField(
        max_length=50,
        unique=True
    )

    department = models.CharField(
        max_length=200
    )

    email = models.EmailField(
        unique=True,
        blank=True,
        null=True
    )

    university = models.CharField(
        max_length=200,
        blank=True
    )

    profile_picture = models.ImageField(
    upload_to="profile_pictures/",
    blank=True,
    null=True
)

    def __str__(self):
        return self.name


# =========================================================
# SEMESTER MODEL
# =========================================================

class Semester(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="semesters"
    )

    level = models.CharField(
        max_length=20
    )

    semester = models.CharField(
        max_length=50
    )

    def __str__(self):

        return (
            f"{self.student.name} - "
            f"{self.level} - "
            f"{self.semester}"
        )


# =========================================================
# COURSE MODEL
# =========================================================

class Course(models.Model):

    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="courses"
    )

    course_code = models.CharField(
        max_length=20
    )

    course_unit = models.PositiveIntegerField()

    grade = models.CharField(
        max_length=1
    )

    def __str__(self):

        return self.course_code

class CourseRetake(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE
    )

    original_course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="retake_records"
    )

    status = models.CharField(
        max_length=30,
        choices=[
            ("pending", "Pending Retake"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
        ],
        default="pending"
    )

    retake_grade = models.CharField(
        max_length=2,
        blank=True,
        null=True
    )

    notes = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):

        return (
            f"{self.student.matric_number} - "
            f"{self.original_course.course_code}"
        )


class Notification(models.Model):

    NOTIFICATION_TYPES = [
        ("exam", "Exam Reminder"),
        ("cgpa", "CGPA Risk"),
        ("academic", "Academic"),
        ("system", "System"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    title = models.CharField(
        max_length=200
    )

    message = models.TextField()

    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default="system"
    )

    is_read = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.student.name} - {self.title}"

    class Meta:
        ordering = ["-created_at"]


class ExamReminder(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="exam_reminders"
    )

    course_code = models.CharField(
        max_length=20
    )

    course_name = models.CharField(
        max_length=200
    )

    exam_date = models.DateField()

    exam_time = models.TimeField(
        blank=True,
        null=True
    )

    venue = models.CharField(
        max_length=200,
        blank=True
    )

    is_completed = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.course_code} - {self.exam_date}"

    class Meta:
        ordering = ["exam_date", "exam_time"]  


# =========================================================
# ACADEMIC TASK / STUDY PLANNER
# =========================================================

class AcademicTask(models.Model):

    TASK_TYPES = [

        (
            "assignment",
            "Assignment"
        ),

        (
            "test",
            "Test"
        ),

        (
            "project",
            "Project"
        ),

        (
            "study",
            "Study Session"
        ),

        (
            "reading",
            "Reading"
        ),

        (
            "presentation",
            "Presentation"
        ),

        (
            "other",
            "Other"
        ),

    ]


    PRIORITY_CHOICES = [

        (
            "low",
            "Low"
        ),

        (
            "medium",
            "Medium"
        ),

        (
            "high",
            "High"
        ),

    ]


    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="academic_tasks"
    )


    title = models.CharField(
        max_length=200
    )


    course_code = models.CharField(
        max_length=30,
        blank=True
    )


    task_type = models.CharField(
        max_length=30,
        choices=TASK_TYPES,
        default="assignment"
    )


    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="medium"
    )


    due_date = models.DateField()


    due_time = models.TimeField(
        blank=True,
        null=True
    )


    description = models.TextField(
        blank=True
    )


    is_completed = models.BooleanField(
        default=False
    )


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )


    def __str__(self):

        return (
            f"{self.student.matric_number} - "
            f"{self.title}"
        )              

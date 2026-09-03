from .models import Notification, Student
from datetime import date
from .models import ExamReminder


def create_notification(
    student,
    title,
    message,
    notification_type="system"
):
    """
    Create a notification only if the same unread
    notification does not already exist.
    """

    existing = Notification.objects.filter(
        student=student,
        title=title,
        message=message,
        is_read=False
    ).exists()

    if not existing:
        Notification.objects.create(
            student=student,
            title=title,
            message=message,
            notification_type=notification_type
        )


def check_cgpa_risk(student):
    """
    Check the student's current CGPA and create
    appropriate academic notifications.
    """

    semesters = student.semesters.all()

    total_quality_points = 0
    total_units = 0

    for semester in semesters:

        for course in semester.courses.all():

            grade_points = {
                "A": 5,
                "B": 4,
                "C": 3,
                "D": 2,
                "E": 1,
                "F": 0,
            }

            points = grade_points.get(
                course.grade.upper(),
                0
            )

            total_quality_points += (
                points * course.course_unit
            )

            total_units += course.course_unit

    # No academic records yet
    if total_units == 0:
        return

    cgpa = total_quality_points / total_units

    # Serious risk
    if cgpa < 2.00:

        create_notification(
            student=student,
            title="Critical CGPA Risk",
            message=(
                f"Your current CGPA is {cgpa:.2f}. "
                "Your academic performance is currently "
                "at serious risk. Consider improving your "
                "grades in your upcoming semesters."
            ),
            notification_type="cgpa"
        )

    # Moderate risk
    elif cgpa < 2.50:

        create_notification(
            student=student,
            title="CGPA Risk Alert",
            message=(
                f"Your current CGPA is {cgpa:.2f}. "
                "You are below the recommended 2.50 level. "
                "Try to improve your GPA in your next semester."
            ),
            notification_type="cgpa"
        )

    # Good performance
    elif cgpa >= 4.00:

        create_notification(
            student=student,
            title="Excellent Academic Performance",
            message=(
                f"Excellent! Your current CGPA is {cgpa:.2f}. "
                "Keep up the good work."
            ),
            notification_type="academic"
        )

    # Good but room for improvement
    elif cgpa >= 3.00:

        create_notification(
            student=student,
            title="Good Academic Progress",
            message=(
                f"Your current CGPA is {cgpa:.2f}. "
                "You are making good academic progress. "
                "Keep working toward your academic goals."
            ),
            notification_type="academic"
        )


def check_exam_reminders(student):

    today = date.today()

    exams = ExamReminder.objects.filter(
        student=student,
        is_completed=False,
        exam_date__gte=today
    )

    for exam in exams:

        days_left = (
            exam.exam_date - today
        ).days

        # ---------------------------------------------
        # EXAM TODAY
        # ---------------------------------------------

        if days_left == 0:

            create_notification(
                student=student,
                title="Exam Today",
                message=(
                    f"{exam.course_code} - "
                    f"{exam.course_name} is scheduled for today."
                ),
                notification_type="exam"
            )

        # ---------------------------------------------
        # EXAM TOMORROW
        # ---------------------------------------------

        elif days_left == 1:

            create_notification(
                student=student,
                title="Exam Tomorrow",
                message=(
                    f"{exam.course_code} - "
                    f"{exam.course_name} is tomorrow."
                ),
                notification_type="exam"
            )

        # ---------------------------------------------
        # EXAM IN 3 DAYS
        # ---------------------------------------------

        elif days_left == 3:

            create_notification(
                student=student,
                title="Exam in 3 Days",
                message=(
                    f"{exam.course_code} - "
                    f"{exam.course_name} is in 3 days."
                ),
                notification_type="exam"
            )

        # ---------------------------------------------
        # EXAM IN 7 DAYS
        # ---------------------------------------------

        elif days_left == 7:

            create_notification(
                student=student,
                title="Exam in 7 Days",
                message=(
                    f"{exam.course_code} - "
                    f"{exam.course_name} is in 7 days."
                ),
                notification_type="exam"
            )        
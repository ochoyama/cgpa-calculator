from datetime import date, timedelta

from django.http import FileResponse, Http404
from django.contrib.staticfiles import finders

import json

from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.http import require_POST

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import (
    Student,
    Semester,
    Course,
    Notification,
    ExamReminder,
    CourseRetake,
    AcademicTask,
    ContactMessage,
)
from .notifications import (
    check_cgpa_risk,
    check_exam_reminders,
)

from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

# =========================================================
# CREATE ACADEMIC PLANNER NOTIFICATIONS
# =========================================================

def create_academic_task_notifications(student):

    today = date.today()

    tomorrow = today + timedelta(days=1)

    three_days = today + timedelta(days=3)


    tasks = AcademicTask.objects.filter(
        student=student,
        is_completed=False
    )


    for task in tasks:

        # =================================================
        # OVERDUE TASK
        # =================================================

        if task.due_date < today:

            title = (
                f"⚠️ Overdue Task: {task.title}"
            )

            message = (
                f"{task.title} was due on "
                f"{task.due_date.strftime('%b %d, %Y')}."
            )

            if task.course_code:

                message += (
                    f" Course: {task.course_code}."
                )


            Notification.objects.get_or_create(

                student=student,

                title=title,

                message=message,

                notification_type="academic",

            )


        # =================================================
        # DUE TODAY
        # =================================================

        elif task.due_date == today:

            title = (
                f"⏰ Due Today: {task.title}"
            )

            message = (
                f"{task.title} is due today."
            )

            if task.due_time:

                message += (
                    f" Time: "
                    f"{task.due_time.strftime('%I:%M %p')}."
                )


            if task.course_code:

                message += (
                    f" Course: {task.course_code}."
                )


            Notification.objects.get_or_create(

                student=student,

                title=title,

                message=message,

                notification_type="academic",

            )


        # =================================================
        # DUE TOMORROW
        # =================================================

        elif task.due_date == tomorrow:

            title = (
                f"📌 Due Tomorrow: {task.title}"
            )

            message = (
                f"{task.title} is due tomorrow."
            )

            if task.course_code:

                message += (
                    f" Course: {task.course_code}."
                )


            Notification.objects.get_or_create(

                student=student,

                title=title,

                message=message,

                notification_type="academic",

            )


        # =================================================
        # DUE WITHIN 3 DAYS
        # =================================================

        elif (
            tomorrow
            <
            task.due_date
            <=
            three_days
        ):

            days_left = (
                task.due_date
                -
                today
            ).days


            title = (
                f"📅 Upcoming Deadline: {task.title}"
            )

            message = (
                f"{task.title} is due in "
                f"{days_left} days."
            )

            if task.course_code:

                message += (
                    f" Course: {task.course_code}."
                )


            Notification.objects.get_or_create(

                student=student,

                title=title,

                message=message,

                notification_type="academic",

            )


# =========================================================
# GRADE POINTS
# =========================================================

GRADE_POINTS = {
    "A": 5,
    "B": 4,
    "C": 3,
    "D": 2,
    "E": 1,
    "F": 0,
}


# =========================================================
# CLASS OF DEGREE
# =========================================================

def get_class_of_degree(cgpa):

    if cgpa >= 4.50:
        return "First Class"

    elif cgpa >= 3.50:
        return "Second Class Upper"

    elif cgpa >= 2.40:
        return "Second Class Lower"

    elif cgpa >= 1.50:
        return "Third Class"

    elif cgpa >= 1.00:
        return "Pass"

    else:
        return "Fail"


# =========================================================
# CALCULATE STUDENT CGPA
# =========================================================

def calculate_student_cgpa(student):

    total_units = 0
    total_quality_points = 0

    semesters = student.semesters.all()

    for semester in semesters:

        courses = semester.courses.all()

        for course in courses:

            point = GRADE_POINTS.get(
                course.grade,
                0
            )

            total_units += course.course_unit

            total_quality_points += (
                course.course_unit * point
            )

    if total_units > 0:

        cgpa = (
            total_quality_points /
            total_units
        )

    else:

        cgpa = 0

    return {
        "cgpa": round(cgpa, 2),
        "total_units": total_units,
        "total_quality_points": total_quality_points,
    }


# =========================================================
# HOME / CGPA CALCULATOR
# =========================================================

@login_required
def home(request):

    result = None

    # -----------------------------------------------------
    # GET LOGGED-IN STUDENT
    # -----------------------------------------------------

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile was not found."
        )

        logout(request)

        return redirect("login")

    # -----------------------------------------------------
    # PROCESS FORM
    # -----------------------------------------------------

    if request.method == "POST":

        level = request.POST.get("level")

        semester_name = request.POST.get("semester")

        courses = request.POST.getlist("course")

        units = request.POST.getlist("unit")

        grades = request.POST.getlist("grade")

        # -------------------------------------------------
        # REQUIRED FIELDS
        # -------------------------------------------------

        if not level or not semester_name:

            result = {
                "error":
                    "Please select a level and semester."
            }

            return render(
                request,
                "calculator/home.html",
                {
                    "result": result,
                    "student": student,
                }
            )

        # -------------------------------------------------
        # CHECK DUPLICATE SEMESTER
        # -------------------------------------------------

        semester_exists = Semester.objects.filter(
            student=student,
            level=level,
            semester=semester_name
        ).exists()

        if semester_exists:

            result = {
                "error": (
                    f"{level} Level - "
                    f"{semester_name} already exists "
                    "for this student."
                ),
                "matric_number":
                    student.matric_number
            }

            return render(
                request,
                "calculator/home.html",
                {
                    "result": result,
                    "student": student,
                }
            )

        # -------------------------------------------------
        # CREATE SEMESTER
        # -------------------------------------------------

        semester = Semester.objects.create(
            student=student,
            level=level,
            semester=semester_name
        )

        semester_units = 0
        semester_quality_points = 0
        courses_added = 0

        # -------------------------------------------------
        # SAVE COURSES
        # -------------------------------------------------

        for course, unit, grade in zip(
            courses,
            units,
            grades
        ):

            if not course or not unit:
                continue

            if grade not in GRADE_POINTS:
                continue

            try:

                unit = int(unit)

            except (ValueError, TypeError):

                continue

            if unit <= 0:
                continue

            point = GRADE_POINTS[grade]

            quality_point = unit * point

            semester_units += unit

            semester_quality_points += quality_point

            Course.objects.create(
                semester=semester,
                course_code=course.strip(),
                course_unit=unit,
                grade=grade
            )

            courses_added += 1

        # -------------------------------------------------
        # CHECK COURSES
        # -------------------------------------------------

        if courses_added == 0:

            semester.delete()

            result = {
                "error":
                    "Please add at least one valid course."
            }

            return render(
                request,
                "calculator/home.html",
                {
                    "result": result,
                    "student": student,
                }
            )

        # -------------------------------------------------
        # SEMESTER GPA
        # -----------------------------------------------------

        semester_gpa = (
            semester_quality_points /
            semester_units
        )

        # -------------------------------------------------
        # CUMULATIVE CGPA
        # -------------------------------------------------

        cgpa_data = calculate_student_cgpa(student)

        cgpa = cgpa_data["cgpa"]

        # -------------------------------------------------
        # CLASS OF DEGREE
        # -------------------------------------------------

        class_of_degree = get_class_of_degree(cgpa)

        # -------------------------------------------------
        # RESULT
        # -------------------------------------------------

        result = {
            "cgpa": cgpa,

            "semester_gpa":
                round(
                    semester_gpa,
                    2
                ),

            "total_units":
                cgpa_data["total_units"],

            "total_quality_points":
                cgpa_data["total_quality_points"],

            "class_of_degree":
                class_of_degree,

            "level":
                level,

            "semester":
                semester_name,

            "student_name":
                student.name,

            "matric_number":
                student.matric_number,
        }

    # -----------------------------------------------------
    # RENDER HOME
    # -----------------------------------------------------

    return render(
        request,
        "calculator/home.html",
        {
            "result": result,
            "student": student,
        }
    )


# =========================================================
# ACADEMIC RECORD
# =========================================================

@login_required
def academic_record(request, matric_number):

    # -----------------------------------------------------
    # GET LOGGED-IN STUDENT
    # -----------------------------------------------------

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        return render(
            request,
            "calculator/not_found.html"
        )

    # -----------------------------------------------------
    # SECURITY CHECK
    # -----------------------------------------------------

    if student.matric_number != matric_number:

        return render(
            request,
            "calculator/not_found.html"
        )

    # -----------------------------------------------------
    # GET SEMESTERS
    # -----------------------------------------------------

    semesters = student.semesters.all().order_by(
        "level",
        "semester"
    )

    total_units = 0
    total_quality_points = 0

    semester_results = []

    # -----------------------------------------------------
    # PROCESS SEMESTERS
    # -----------------------------------------------------

    for semester in semesters:

        semester_units = 0
        semester_quality_points = 0

        courses = semester.courses.all()

        course_results = []

        # -------------------------------------------------
        # PROCESS COURSES
        # -------------------------------------------------

        for course in courses:

            point = GRADE_POINTS.get(
                course.grade,
                0
            )

            quality_point = (
                course.course_unit *
                point
            )

            semester_units += course.course_unit

            semester_quality_points += quality_point

            total_units += course.course_unit

            total_quality_points += quality_point

            course_results.append({
                "course": course,
                "point": point,
                "quality_point": quality_point
            })

        # -------------------------------------------------
        # SEMESTER GPA
        # -------------------------------------------------

        if semester_units > 0:

            semester_gpa = (
                semester_quality_points /
                semester_units
            )

        else:

            semester_gpa = 0

        # -------------------------------------------------
        # STORE RESULT
        # -------------------------------------------------

        semester_results.append({
            "semester": semester,

            "courses":
                course_results,

            "units":
                semester_units,

            "quality_points":
                semester_quality_points,

            "gpa":
                round(
                    semester_gpa,
                    2
                )
        })

    # -----------------------------------------------------
    # FINAL CGPA
    # -----------------------------------------------------

    if total_units > 0:

        cgpa = (
            total_quality_points /
            total_units
        )

    else:

        cgpa = 0

    cgpa = round(cgpa, 2)

    # -----------------------------------------------------
    # CLASS OF DEGREE
    # -----------------------------------------------------

    class_of_degree = get_class_of_degree(cgpa)

    # -----------------------------------------------------
    # CONTEXT
    # -----------------------------------------------------

    context = {
        "student": student,

        "semester_results":
            semester_results,

        "cgpa":
            cgpa,

        "total_units":
            total_units,

        "total_quality_points":
            total_quality_points,

        "class_of_degree":
            class_of_degree
    }

    # -----------------------------------------------------
    # RENDER
    # -----------------------------------------------------

    return render(
        request,
        "calculator/academic_record.html",
        context
    )


# =========================================================
# DELETE SEMESTER
# =========================================================

@login_required
def delete_semester(request, semester_id):

    try:

        semester = Semester.objects.get(
            id=semester_id
        )

    except Semester.DoesNotExist:

        return render(
            request,
            "calculator/not_found.html"
        )

    student = semester.student

    # -----------------------------------------------------
    # SECURITY CHECK
    # -----------------------------------------------------

    if student.user != request.user:

        return render(
            request,
            "calculator/not_found.html"
        )

    # -----------------------------------------------------
    # DELETE
    # -----------------------------------------------------

    if request.method == "POST":

        semester.delete()

        return redirect(
            "academic_record",
            matric_number=student.matric_number
        )

    # -----------------------------------------------------
    # CONFIRMATION PAGE
    # -----------------------------------------------------

    return render(
        request,
        "calculator/delete_semester.html",
        {
            "semester": semester,
            "student": student
        }
    )


# =========================================================
# EDIT COURSE
# =========================================================

@login_required
def edit_course(request, course_id):

    try:

        course = Course.objects.get(
            id=course_id
        )

    except Course.DoesNotExist:

        return render(
            request,
            "calculator/not_found.html"
        )

    semester = course.semester

    student = semester.student

    # -----------------------------------------------------
    # SECURITY CHECK
    # -----------------------------------------------------

    if student.user != request.user:

        return render(
            request,
            "calculator/not_found.html"
        )

    # -----------------------------------------------------
    # UPDATE COURSE
    # -----------------------------------------------------

    if request.method == "POST":

        course_code = request.POST.get(
            "course_code"
        )

        course_unit = request.POST.get(
            "course_unit"
        )

        grade = request.POST.get(
            "grade"
        )

        # -------------------------------------------------
        # COURSE CODE VALIDATION
        # -------------------------------------------------

        if not course_code:

            return render(
                request,
                "calculator/edit_course.html",
                {
                    "course": course,
                    "semester": semester,
                    "student": student,
                    "error":
                        "Course code is required."
                }
            )

        # -------------------------------------------------
        # GRADE VALIDATION
        # -------------------------------------------------

        if grade not in GRADE_POINTS:

            return render(
                request,
                "calculator/edit_course.html",
                {
                    "course": course,
                    "semester": semester,
                    "student": student,
                    "error":
                        "Please select a valid grade."
                }
            )

        # -------------------------------------------------
        # UNIT VALIDATION
        # -------------------------------------------------

        try:

            course_unit = int(course_unit)

        except (ValueError, TypeError):

            return render(
                request,
                "calculator/edit_course.html",
                {
                    "course": course,
                    "semester": semester,
                    "student": student,
                    "error":
                        "Course unit must be a number."
                }
            )

        if course_unit <= 0:

            return render(
                request,
                "calculator/edit_course.html",
                {
                    "course": course,
                    "semester": semester,
                    "student": student,
                    "error":
                        "Course unit must be greater than zero."
                }
            )

        # -------------------------------------------------
        # SAVE CHANGES
        # -------------------------------------------------

        course.course_code = course_code.strip()

        course.course_unit = course_unit

        course.grade = grade

        course.save()

        # -------------------------------------------------
        # RETURN TO RECORD
        # -------------------------------------------------

        return redirect(
            "academic_record",
            matric_number=student.matric_number
        )

    # -----------------------------------------------------
    # DISPLAY EDIT PAGE
    # -----------------------------------------------------

    return render(
        request,
        "calculator/edit_course.html",
        {
            "course": course,
            "semester": semester,
            "student": student
        }
    )


# =========================================================
# DELETE COURSE
# =========================================================

@login_required
def delete_course(request, course_id):

    try:

        course = Course.objects.get(
            id=course_id
        )

    except Course.DoesNotExist:

        return render(
            request,
            "calculator/not_found.html"
        )

    semester = course.semester

    student = semester.student

    # -----------------------------------------------------
    # SECURITY CHECK
    # -----------------------------------------------------

    if student.user != request.user:

        return render(
            request,
            "calculator/not_found.html"
        )

    # -----------------------------------------------------
    # DELETE COURSE
    # -----------------------------------------------------

    if request.method == "POST":

        course.delete()

        return redirect(
            "academic_record",
            matric_number=student.matric_number
        )

    # -----------------------------------------------------
    # CONFIRMATION PAGE
    # -----------------------------------------------------

    return render(
        request,
        "calculator/delete_course.html",
        {
            "course": course,
            "semester": semester,
            "student": student
        }
    )


# =========================================================
# ADD ANOTHER SEMESTER
# =========================================================

@login_required
def add_semester(request, matric_number):

    # -----------------------------------------------------
    # GET STUDENT
    # -----------------------------------------------------

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        return render(
            request,
            "calculator/not_found.html"
        )

    # -----------------------------------------------------
    # SECURITY CHECK
    # -----------------------------------------------------

    if student.matric_number != matric_number:

        return render(
            request,
            "calculator/not_found.html"
        )

    # -----------------------------------------------------
    # PROCESS FORM
    # -----------------------------------------------------

    if request.method == "POST":

        level = request.POST.get("level")

        semester_name = request.POST.get("semester")

        courses = request.POST.getlist("course")

        units = request.POST.getlist("unit")

        grades = request.POST.getlist("grade")

        # -------------------------------------------------
        # REQUIRED FIELDS
        # -------------------------------------------------

        if not level or not semester_name:

            return render(
                request,
                "calculator/add_semester.html",
                {
                    "student": student,
                    "error":
                        "Please select a level and semester."
                }
            )

        # -------------------------------------------------
        # DUPLICATE SEMESTER
        # -------------------------------------------------

        semester_exists = Semester.objects.filter(
            student=student,
            level=level,
            semester=semester_name
        ).exists()

        if semester_exists:

            error = (
                f"{level} Level - "
                f"{semester_name} already exists "
                "for this student."
            )

            return render(
                request,
                "calculator/add_semester.html",
                {
                    "student": student,
                    "error": error
                }
            )

        # -------------------------------------------------
        # CREATE SEMESTER
        # -------------------------------------------------

        semester = Semester.objects.create(
            student=student,
            level=level,
            semester=semester_name
        )

        courses_added = 0

        # -------------------------------------------------
        # SAVE COURSES
        # -------------------------------------------------

        for course, unit, grade in zip(
            courses,
            units,
            grades
        ):

            if not course or not unit:
                continue

            if grade not in GRADE_POINTS:
                continue

            try:

                unit = int(unit)

            except (ValueError, TypeError):

                continue

            if unit <= 0:
                continue

            Course.objects.create(
                semester=semester,
                course_code=course.strip(),
                course_unit=unit,
                grade=grade
            )

            courses_added += 1

        # -------------------------------------------------
        # REMOVE EMPTY SEMESTER
        # -------------------------------------------------

        if courses_added == 0:

            semester.delete()

            return render(
                request,
                "calculator/add_semester.html",
                {
                    "student": student,
                    "error":
                        "Please add at least one valid course."
                }
            )

        # -------------------------------------------------
        # RETURN TO RECORD
        # -------------------------------------------------

        return redirect(
            "academic_record",
            matric_number=student.matric_number
        )

    # -----------------------------------------------------
    # DISPLAY FORM
    # -----------------------------------------------------

    return render(
        request,
        "calculator/add_semester.html",
        {
            "student": student
        }
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@login_required
def dashboard(request, matric_number):

    # -----------------------------------------------------
    # GET LOGGED-IN STUDENT
    # -----------------------------------------------------

    try:
        student = Student.objects.get(
            user=request.user
        )
    except Student.DoesNotExist:
        messages.error(
            request,
            "Student profile was not found."
        )
        logout(request)
        return redirect("login")

    # -----------------------------------------------------
    # SECURITY CHECK
    # -----------------------------------------------------

    if student.matric_number != matric_number:
        return render(
            request,
            "calculator/not_found.html"
        )

    # -----------------------------------------------------
    # AUTOMATIC NOTIFICATION CHECKS
    # -----------------------------------------------------

    check_cgpa_risk(student)
    check_exam_reminders(student)

    # -----------------------------------------------------
    # UNREAD NOTIFICATIONS
    # -----------------------------------------------------

    unread_count = Notification.objects.filter(
        student=student,
        is_read=False
    ).count()

    # -----------------------------------------------------
    # OVERALL CGPA DATA
    # -----------------------------------------------------

    cgpa_data = calculate_student_cgpa(student)

    cgpa = cgpa_data["cgpa"]
    total_units = cgpa_data["total_units"]
    total_quality_points = cgpa_data["total_quality_points"]

    # -----------------------------------------------------
    # CLASS OF DEGREE
    # -----------------------------------------------------

    class_of_degree = get_class_of_degree(cgpa)

    # -----------------------------------------------------
    # COUNTS
    # -----------------------------------------------------

    semester_count = student.semesters.count()

    course_count = Course.objects.filter(
        semester__student=student
    ).count()

    # -----------------------------------------------------
    # SEMESTER PERFORMANCE
    # -----------------------------------------------------

    semesters = student.semesters.all().order_by(
        "level",
        "semester"
    )

    semester_performance = []

    cumulative_units = 0
    cumulative_quality_points = 0

    for semester in semesters:

        semester_units = 0
        semester_quality_points = 0

        courses = semester.courses.all()

        for course in courses:

            point = GRADE_POINTS.get(
                course.grade,
                0
            )

            quality_point = (
                course.course_unit * point
            )

            semester_units += course.course_unit
            semester_quality_points += quality_point

        cumulative_units += semester_units
        cumulative_quality_points += semester_quality_points

        if semester_units > 0:
            semester_gpa = (
                semester_quality_points /
                semester_units
            )
        else:
            semester_gpa = 0

        if cumulative_units > 0:
            cumulative_cgpa = (
                cumulative_quality_points /
                cumulative_units
            )
        else:
            cumulative_cgpa = 0

        semester_performance.append({
            "semester": semester,
            "units": semester_units,
            "quality_points": semester_quality_points,
            "gpa": round(semester_gpa, 2),
            "cumulative_cgpa": round(cumulative_cgpa, 2),
        })

    # -----------------------------------------------------
    # DASHBOARD CONTEXT
    # -----------------------------------------------------

    context = {
        "student": student,
        "cgpa": cgpa,
        "total_units": total_units,
        "total_quality_points": total_quality_points,
        "class_of_degree": class_of_degree,
        "semester_count": semester_count,
        "course_count": course_count,
        "semester_performance": semester_performance,
        "unread_count": unread_count,
    }

    return render(
        request,
        "calculator/dashboard.html",
        context
    )


# =========================================================
# STUDENT REGISTRATION
# =========================================================

def register(request):

    # -----------------------------------------------------
    # IF ALREADY LOGGED IN
    # -----------------------------------------------------

    if request.user.is_authenticated:

        try:

            student = Student.objects.get(
                user=request.user
            )

            return redirect(
                "dashboard",
                matric_number=student.matric_number
            )

        except Student.DoesNotExist:

            logout(request)

    # -----------------------------------------------------
    # PROCESS REGISTRATION
    # -----------------------------------------------------

    if request.method == "POST":

        # -------------------------------------------------
        # GET FORM DATA
        # -------------------------------------------------

        matric_number = request.POST.get(
            "matric_number"
        )

        password = request.POST.get(
            "password"
        )

        confirm_password = request.POST.get(
            "confirm_password"
        )

        name = request.POST.get(
            "name"
        )

        department = request.POST.get(
            "department"
        )

        university = request.POST.get(
            "university"
        )

        email = request.POST.get(
            "email"
        )

        # -------------------------------------------------
        # CLEAN DATA
        # -------------------------------------------------

        matric_number = (
            matric_number.strip()
            if matric_number
            else ""
        )

        name = (
            name.strip()
            if name
            else ""
        )

        department = (
            department.strip()
            if department
            else ""
        )

        university = (
            university.strip()
            if university
            else ""
        )

        email = (
            email.strip().lower()
            if email
            else ""
        )

        # -------------------------------------------------
        # REQUIRED FIELDS
        # -------------------------------------------------

        if not matric_number:

            messages.error(
                request,
                "Please enter your matric number."
            )

            return render(
                request,
                "calculator/register.html"
            )

        if not password:

            messages.error(
                request,
                "Please enter a password."
            )

            return render(
                request,
                "calculator/register.html"
            )

        if not confirm_password:

            messages.error(
                request,
                "Please confirm your password."
            )

            return render(
                request,
                "calculator/register.html"
            )

        if not name:

            messages.error(
                request,
                "Please enter your name."
            )

            return render(
                request,
                "calculator/register.html"
            )

        if not department:

            messages.error(
                request,
                "Please enter your department."
            )

            return render(
                request,
                "calculator/register.html"
            )

        if not email:

            messages.error(
                request,
                "Please enter your email."
            )

            return render(
                request,
                "calculator/register.html"
            )

        # -------------------------------------------------
        # PASSWORD MATCH
        # -------------------------------------------------

        if password != confirm_password:

            messages.error(
                request,
                "Passwords do not match."
            )

            return render(
                request,
                "calculator/register.html"
            )

        # -------------------------------------------------
        # CHECK MATRIC NUMBER
        # -------------------------------------------------

        if Student.objects.filter(
            matric_number=matric_number
        ).exists():

            messages.error(
                request,
                "This matric number is already registered."
            )

            return render(
                request,
                "calculator/register.html"
            )

        # -------------------------------------------------
        # CHECK USERNAME
        # -------------------------------------------------

        if User.objects.filter(
            username=matric_number
        ).exists():

            messages.error(
                request,
                "This matric number is already associated with an account."
            )

            return render(
                request,
                "calculator/register.html"
            )

        # -------------------------------------------------
        # CHECK EMAIL
        # -------------------------------------------------

        if Student.objects.filter(
            email=email
        ).exists():

            messages.error(
                request,
                "This email is already registered."
            )

            return render(
                request,
                "calculator/register.html"
            )

        if User.objects.filter(
            email=email
        ).exists():

            messages.error(
                request,
                "This email is already associated with an account."
            )

            return render(
                request,
                "calculator/register.html"
            )

        # -------------------------------------------------
        # CREATE USER AND STUDENT
        # -------------------------------------------------

        user = None

        try:

            user = User.objects.create_user(
                username=matric_number,
                email=email,
                password=password
            )

            student = Student.objects.create(
                user=user,
                name=name,
                matric_number=matric_number,
                department=department,
                email=email,
                university=university
            )

        except Exception as e:

            if user is not None:
                user.delete()

            messages.error(
                request,
                f"Registration failed: {str(e)}"
            )

            return render(
                request,
                "calculator/register.html"
            )

        # -------------------------------------------------
        # AUTOMATIC LOGIN
        # -------------------------------------------------

        login(
            request,
            user
        )

        # -------------------------------------------------
        # SUCCESS MESSAGE
        # -------------------------------------------------

        messages.success(
            request,
            "Registration successful! Welcome to the CGPA Calculator."
        )

        # -------------------------------------------------
        # GO TO DASHBOARD
        # -------------------------------------------------

        return redirect(
            "dashboard",
            matric_number=student.matric_number
        )

    # -----------------------------------------------------
    # DISPLAY REGISTRATION PAGE
    # -----------------------------------------------------

    return render(
        request,
        "calculator/register.html"
    )


# =========================================================
# STUDENT LOGIN
# =========================================================

def login_view(request):

    # -----------------------------------------------------
    # IF ALREADY LOGGED IN
    # -----------------------------------------------------

    if request.user.is_authenticated:

        try:

            student = Student.objects.get(
                user=request.user
            )

            return redirect(
                "dashboard",
                matric_number=student.matric_number
            )

        except Student.DoesNotExist:

            logout(request)

    # -----------------------------------------------------
    # PROCESS LOGIN
    # -----------------------------------------------------

    if request.method == "POST":

        matric_number = request.POST.get(
            "matric_number",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        # -------------------------------------------------
        # CHECK MATRIC NUMBER
        # -------------------------------------------------

        if not matric_number:

            messages.error(
                request,
                "Please enter your matric number."
            )

            return render(
                request,
                "calculator/login.html"
            )

        # -------------------------------------------------
        # CHECK PASSWORD
        # -------------------------------------------------

        if not password:

            messages.error(
                request,
                "Please enter your password."
            )

            return render(
                request,
                "calculator/login.html"
            )

        # -------------------------------------------------
        # FIND STUDENT
        # -------------------------------------------------

        try:

            student = Student.objects.select_related(
                "user"
            ).get(
                matric_number=matric_number
            )

        except Student.DoesNotExist:

            messages.error(
                request,
                "Invalid matric number or password."
            )

            return render(
                request,
                "calculator/login.html"
            )

        # -------------------------------------------------
        # AUTHENTICATE
        # -------------------------------------------------

        user = authenticate(
            request,
            username=student.user.username,
            password=password
        )

        # -------------------------------------------------
        # INVALID LOGIN
        # -------------------------------------------------

        if user is None:

            messages.error(
                request,
                "Invalid matric number or password."
            )

            return render(
                request,
                "calculator/login.html"
            )

        # -------------------------------------------------
        # LOGIN USER
        # -------------------------------------------------

        login(
            request,
            user
        )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        messages.success(
            request,
            "Login successful. Welcome back!"
        )

        # -------------------------------------------------
        # GO TO DASHBOARD
        # -------------------------------------------------

        return redirect(
            "dashboard",
            matric_number=student.matric_number
        )

    # -----------------------------------------------------
    # DISPLAY LOGIN PAGE
    # -----------------------------------------------------

    return render(
        request,
        "calculator/login.html"
    )


# =========================================================
# STUDENT LOGOUT
# =========================================================

@login_required
def logout_view(request):

    logout(request)

    messages.success(
        request,
        "You have been logged out successfully."
    )

    return redirect(
        "login"
    )


# =========================================================
# STUDENT PROFILE
# =========================================================

@login_required
def profile(request):

    # -----------------------------------------------------
    # GET LOGGED-IN STUDENT
    # -----------------------------------------------------

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile was not found."
        )

        logout(request)

        return redirect("login")

    # -----------------------------------------------------
    # UPDATE PROFILE
    # -----------------------------------------------------

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip().lower()

        department = request.POST.get(
            "department",
            ""
        ).strip()

        university = request.POST.get(
            "university",
            ""
        ).strip()

        # -------------------------------------------------
        # GET UPLOADED PROFILE PICTURE
        # -------------------------------------------------

        profile_picture = request.FILES.get(
            "profile_picture"
        )

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not name:

            messages.error(
                request,
                "Name cannot be empty."
            )

            return render(
                request,
                "calculator/profile.html",
                {
                    "student": student
                }
            )

        if not email:

            messages.error(
                request,
                "Email cannot be empty."
            )

            return render(
                request,
                "calculator/profile.html",
                {
                    "student": student
                }
            )

        if not department:

            messages.error(
                request,
                "Department cannot be empty."
            )

            return render(
                request,
                "calculator/profile.html",
                {
                    "student": student
                }
            )

        # -------------------------------------------------
        # CHECK STUDENT EMAIL
        # -------------------------------------------------

        if Student.objects.exclude(
            pk=student.pk
        ).filter(
            email=email
        ).exists():

            messages.error(
                request,
                "Another student is already using this email."
            )

            return render(
                request,
                "calculator/profile.html",
                {
                    "student": student
                }
            )

        # -------------------------------------------------
        # CHECK USER EMAIL
        # -------------------------------------------------

        if User.objects.exclude(
            pk=request.user.pk
        ).filter(
            email=email
        ).exists():

            messages.error(
                request,
                "Another account is already using this email."
            )

            return render(
                request,
                "calculator/profile.html",
                {
                    "student": student
                }
            )

        # -------------------------------------------------
        # SAVE STUDENT INFORMATION
        # -------------------------------------------------

        student.name = name

        student.email = email

        student.department = department

        student.university = university

        # -------------------------------------------------
        # SAVE PROFILE PICTURE
        # -------------------------------------------------

        if profile_picture:

            student.profile_picture = profile_picture

        student.save()

        # -------------------------------------------------
        # UPDATE DJANGO USER EMAIL
        # -------------------------------------------------

        request.user.email = email

        request.user.save(
            update_fields=["email"]
        )

        # -------------------------------------------------
        # SUCCESS MESSAGE
        # -------------------------------------------------

        messages.success(
            request,
            "Your profile has been updated successfully."
        )

        return redirect(
            "profile"
        )

    # -----------------------------------------------------
    # DISPLAY PROFILE
    # -----------------------------------------------------

    return render(
        request,
        "calculator/profile.html",
        {
            "student": student
        }
    )


# =========================================================
# BACKWARD COMPATIBILITY ALIASES
# =========================================================

student_login = login_view

student_logout = logout_view

@login_required
def notifications_view(request):
    """
    Display notifications belonging to the logged-in student.
    """

    student = get_object_or_404(
        Student,
        user=request.user
    )

    notifications = Notification.objects.filter(
        student=student
    ).order_by("-created_at")

    unread_count = notifications.filter(
        is_read=False
    ).count()

    context = {
        "student": student,
        "notifications": notifications,
        "unread_count": unread_count,
    }

    return render(
        request,
        "calculator/notifications.html",
        context
    )


@login_required
def mark_notification_read(request, notification_id):
    """
    Mark one notification as read.
    """

    student = get_object_or_404(
        Student,
        user=request.user
    )

    notification = get_object_or_404(
        Notification,
        id=notification_id,
        student=student
    )

    notification.is_read = True
    notification.save(
        update_fields=["is_read"]
    )

    return redirect("notifications")


@login_required
def mark_all_notifications_read(request):
    """
    Mark all notifications belonging to the student as read.
    """

    student = get_object_or_404(
        Student,
        user=request.user
    )

    Notification.objects.filter(
        student=student,
        is_read=False
    ).update(
        is_read=True
    )

    return redirect("notifications")


@login_required
def delete_notification(request, notification_id):
    """
    Delete one notification belonging to the logged-in student.
    """

    student = get_object_or_404(
        Student,
        user=request.user
    )

    notification = get_object_or_404(
        Notification,
        id=notification_id,
        student=student
    )

    notification.delete()

    messages.success(
        request,
        "Notification deleted."
    )

    return redirect("notifications")


# =========================================================
# EXAM REMINDERS
# =========================================================

@login_required
def exam_reminders(request):
    """
    Display the logged-in student's exam reminders.
    """

    student = get_object_or_404(
        Student,
        user=request.user
    )

    today = date.today()

    exams = ExamReminder.objects.filter(
        student=student
    ).order_by(
        "exam_date",
        "exam_time"
    )

    upcoming_exams = exams.filter(
        exam_date__gte=today,
        is_completed=False
    )

    past_exams = exams.filter(
        exam_date__lt=today
    )

    completed_exams = exams.filter(
        is_completed=True
    )

    context = {
        "student": student,
        "exams": exams,
        "upcoming_exams": upcoming_exams,
        "past_exams": past_exams,
        "completed_exams": completed_exams,
    }

    return render(
        request,
        "calculator/exam_reminders.html",
        context
    )


@login_required
def add_exam_reminder(request):
    """
    Add a new exam reminder.
    """

    student = get_object_or_404(
        Student,
        user=request.user
    )

    if request.method == "POST":

        course_code = request.POST.get(
            "course_code",
            ""
        ).strip().upper()

        course_name = request.POST.get(
            "course_name",
            ""
        ).strip()

        exam_date_value = request.POST.get(
            "exam_date",
            ""
        ).strip()

        exam_time = request.POST.get(
            "exam_time",
            ""
        ).strip()

        venue = request.POST.get(
            "venue",
            ""
        ).strip()

        if not course_code or not course_name or not exam_date_value:

            messages.error(
                request,
                "Please fill in all required exam information."
            )

            return render(
                request,
                "calculator/add_exam.html",
                {
                    "student": student
                }
            )

        try:
            parsed_exam_date = date.fromisoformat(
                exam_date_value
            )
        except ValueError:
            messages.error(
                request,
                "Please enter a valid exam date."
            )

            return render(
                request,
                "calculator/add_exam.html",
                {
                    "student": student
                }
            )

        if parsed_exam_date < date.today():

            messages.error(
                request,
                "The exam date cannot be in the past."
            )

            return render(
                request,
                "calculator/add_exam.html",
                {
                    "student": student
                }
            )

        duplicate_exam = ExamReminder.objects.filter(
            student=student,
            course_code__iexact=course_code,
            exam_date=parsed_exam_date,
            is_completed=False
        ).exists()

        if duplicate_exam:

            messages.error(
                request,
                "An exam reminder for this course and date already exists."
            )

            return render(
                request,
                "calculator/add_exam.html",
                {
                    "student": student
                }
            )

        ExamReminder.objects.create(
            student=student,
            course_code=course_code,
            course_name=course_name,
            exam_date=parsed_exam_date,
            exam_time=exam_time if exam_time else None,
            venue=venue,
        )

        # Generate an immediate notification if the exam
        # falls on one of the configured reminder days.
        check_exam_reminders(student)

        messages.success(
            request,
            "Exam reminder added successfully."
        )

        return redirect(
            "exam_reminders"
        )

    return render(
        request,
        "calculator/add_exam.html",
        {
            "student": student
        }
    )


@login_required
def complete_exam(request, exam_id):
    """
    Mark an exam as completed.
    """

    student = get_object_or_404(
        Student,
        user=request.user
    )

    exam = get_object_or_404(
        ExamReminder,
        id=exam_id,
        student=student
    )

    exam.is_completed = True
    exam.save(
        update_fields=["is_completed"]
    )

    messages.success(
        request,
        "Exam marked as completed."
    )

    return redirect(
        "exam_reminders"
    )


@login_required
def delete_exam_reminder(request, exam_id):
    """
    Delete an exam reminder belonging to the logged-in student.
    """

    student = get_object_or_404(
        Student,
        user=request.user
    )

    exam = get_object_or_404(
        ExamReminder,
        id=exam_id,
        student=student
    )

    exam.delete()

    messages.success(
        request,
        "Exam reminder deleted."
    )

    return redirect(
        "exam_reminders"
    )

def offline_view(request):

    return render(
        request,
        "calculator/offline.html"
    )  


# =========================================================
# OFFLINE RESULT SYNC
# =========================================================

@require_POST
def sync_offline_result(request):

    # -----------------------------------------------------
    # USER MUST BE LOGGED IN
    # -----------------------------------------------------

    if not request.user.is_authenticated:

        return JsonResponse(
            {
                "success": False,
                "error": "Your login session has expired."
            },
            status=401
        )


    # -----------------------------------------------------
    # GET STUDENT
    # -----------------------------------------------------

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "error": "Student profile was not found."
            },
            status=404
        )


    # -----------------------------------------------------
    # READ JSON
    # -----------------------------------------------------

    try:

        data = json.loads(
            request.body
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid result data."
            },
            status=400
        )


    # -----------------------------------------------------
    # GET VALUES
    # -----------------------------------------------------

    level = str(
        data.get(
            "level",
            ""
        )
    ).strip()


    semester_name = str(
        data.get(
            "semester",
            ""
        )
    ).strip()


    courses = data.get(
        "courses",
        []
    )


    # -----------------------------------------------------
    # VALID LEVEL
    # -----------------------------------------------------

    valid_levels = {
        "100",
        "200",
        "300",
        "400",
        "500",
        "600",
    }


    if level not in valid_levels:

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid academic level."
            },
            status=400
        )


    # -----------------------------------------------------
    # VALID SEMESTER
    # -----------------------------------------------------

    valid_semesters = {
        "First Semester",
        "Second Semester",
    }


    if semester_name not in valid_semesters:

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid semester."
            },
            status=400
        )


    # -----------------------------------------------------
    # CHECK COURSES
    # -----------------------------------------------------

    if not isinstance(
        courses,
        list
    ) or not courses:

        return JsonResponse(
            {
                "success": False,
                "error": "At least one course is required."
            },
            status=400
        )


    # -----------------------------------------------------
    # CHECK DUPLICATE SEMESTER
    # -----------------------------------------------------

    semester_exists = Semester.objects.filter(

        student=student,

        level=level,

        semester=semester_name

    ).exists()


    if semester_exists:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    f"{level} Level - "
                    f"{semester_name} already exists."
                ),
                "code": "duplicate_semester"
            },
            status=409
        )


    # -----------------------------------------------------
    # VALIDATE COURSES BEFORE SAVING
    # -----------------------------------------------------

    cleaned_courses = []


    for course_data in courses:

        course_code = str(
            course_data.get(
                "course",
                ""
            )
        ).strip().upper()


        grade = str(
            course_data.get(
                "grade",
                ""
            )
        ).strip().upper()


        unit_value = course_data.get(
            "unit"
        )


        if not course_code:

            return JsonResponse(
                {
                    "success": False,
                    "error": "A course code is missing."
                },
                status=400
            )


        if grade not in GRADE_POINTS:

            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        f"Invalid grade for "
                        f"{course_code}."
                    )
                },
                status=400
            )


        try:

            unit = int(
                unit_value
            )

        except (
            TypeError,
            ValueError
        ):

            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        f"Invalid course unit for "
                        f"{course_code}."
                    )
                },
                status=400
            )


        if unit < 1 or unit > 10:

            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        f"Course unit for "
                        f"{course_code} must be "
                        f"between 1 and 10."
                    )
                },
                status=400
            )


        cleaned_courses.append(
            {
                "course_code":
                    course_code,

                "course_unit":
                    unit,

                "grade":
                    grade,
            }
        )


    # -----------------------------------------------------
    # SAVE EVERYTHING AS ONE TRANSACTION
    # -----------------------------------------------------

    try:

        with transaction.atomic():

            semester = Semester.objects.create(

                student=student,

                level=level,

                semester=semester_name

            )


            for course_data in cleaned_courses:

                Course.objects.create(

                    semester=semester,

                    course_code=
                        course_data[
                            "course_code"
                        ],

                    course_unit=
                        course_data[
                            "course_unit"
                        ],

                    grade=
                        course_data[
                            "grade"
                        ]

                )


    except Exception:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "The result could not be saved. "
                    "Please try again."
                )
            },
            status=500
        )


    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    return JsonResponse(
        {
            "success": True,
            "message": (
                f"{level} Level - "
                f"{semester_name} synced successfully."
            ),
            "semester_id": semester.id
        },
        status=201
    )  


# =========================================================
# CGPA GOAL PLANNER
# =========================================================

@login_required
def cgpa_goal_planner(request):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    # =====================================================
    # CURRENT ACADEMIC TOTALS
    # =====================================================

    semesters = Semester.objects.filter(
        student=student
    )


    total_units = 0

    total_quality_points = 0


    for semester in semesters:

        courses = Course.objects.filter(
            semester=semester
        )


        for course in courses:

            point = GRADE_POINTS.get(
                course.grade,
                0
            )


            total_units += (
                course.course_unit
            )


            total_quality_points += (
                course.course_unit
                *
                point
            )


    if total_units > 0:

        current_cgpa = round(
            total_quality_points
            /
            total_units,
            2
        )

    else:

        current_cgpa = 0


    result = None


    # =====================================================
    # HANDLE PLANNER FORM
    # =====================================================

    if request.method == "POST":

        try:

            target_cgpa = float(
                request.POST.get(
                    "target_cgpa"
                )
            )


            next_semester_units = int(
                request.POST.get(
                    "next_semester_units"
                )
            )


            # =============================================
            # VALIDATION
            # =============================================

            if (
                target_cgpa < 0
                or
                target_cgpa > 5
            ):

                raise ValueError(
                    "Target CGPA must be between 0 and 5."
                )


            if (
                next_semester_units <= 0
            ):

                raise ValueError(
                    "Next semester units must be greater than 0."
                )


            total_future_units = (
                total_units
                +
                next_semester_units
            )


            required_quality_points = (
                target_cgpa
                *
                total_future_units
            )


            required_next_semester_points = (
                required_quality_points
                -
                total_quality_points
            )


            required_gpa = (
                required_next_semester_points
                /
                next_semester_units
            )


            required_gpa = round(
                required_gpa,
                2
            )


            # =============================================
            # DETERMINE POSSIBILITY
            # =============================================

            if required_gpa > 5:

                status = "impossible"

                message = (
                    "This target cannot be reached "
                    "in only one semester."
                )


            elif required_gpa <= 0:

                status = "already_reached"

                message = (
                    "You have already reached or "
                    "exceeded this target."
                )


            else:

                status = "possible"

                message = (
                    "Your target is mathematically "
                    "possible next semester."
                )


            result = {

                "target_cgpa":
                    target_cgpa,

                "next_semester_units":
                    next_semester_units,

                "required_gpa":
                    required_gpa,

                "status":
                    status,

                "message":
                    message,

            }


        except (
            TypeError,
            ValueError
        ) as error:

            result = {

                "error":
                    str(error)

            }


    context = {

        "student":
            student,

        "current_cgpa":
            current_cgpa,

        "total_units":
            total_units,

        "total_quality_points":
            total_quality_points,

        "result":
            result,

    }


    return render(
        request,
        "calculator/cgpa_goal_planner.html",
        context
    ) 

# =========================================================
# GRADE SCENARIO SIMULATOR
# =========================================================

@login_required
def grade_scenario_simulator(request):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    # =====================================================
    # CURRENT ACADEMIC TOTALS
    # =====================================================

    semesters = Semester.objects.filter(
        student=student
    )


    current_total_units = 0

    current_total_quality_points = 0


    for semester in semesters:

        courses = Course.objects.filter(
            semester=semester
        )


        for course in courses:

            point = GRADE_POINTS.get(
                course.grade,
                0
            )


            current_total_units += (
                course.course_unit
            )


            current_total_quality_points += (
                course.course_unit
                *
                point
            )


    if current_total_units > 0:

        current_cgpa = round(
            current_total_quality_points
            /
            current_total_units,
            2
        )

    else:

        current_cgpa = 0


    result = None


    # =====================================================
    # HANDLE SIMULATION
    # =====================================================

    if request.method == "POST":

        course_codes = request.POST.getlist(
            "course"
        )

        units = request.POST.getlist(
            "unit"
        )

        grades = request.POST.getlist(
            "grade"
        )


        simulated_units = 0

        simulated_quality_points = 0

        simulated_courses = []


        if not (
            len(course_codes)
            ==
            len(units)
            ==
            len(grades)
        ):

            result = {
                "error":
                    "The course information is incomplete."
            }


        else:

            try:

                for index in range(
                    len(course_codes)
                ):

                    course_code = (
                        course_codes[index]
                        .strip()
                        .upper()
                    )


                    grade = (
                        grades[index]
                        .strip()
                        .upper()
                    )


                    unit = int(
                        units[index]
                    )


                    if not course_code:

                        raise ValueError(
                            "Every course must have a course code."
                        )


                    if grade not in GRADE_POINTS:

                        raise ValueError(
                            f"Invalid grade for {course_code}."
                        )


                    if (
                        unit < 1
                        or
                        unit > 10
                    ):

                        raise ValueError(
                            f"Units for {course_code} must be between 1 and 10."
                        )


                    point = GRADE_POINTS[
                        grade
                    ]


                    quality_point = (
                        unit
                        *
                        point
                    )


                    simulated_units += (
                        unit
                    )


                    simulated_quality_points += (
                        quality_point
                    )


                    simulated_courses.append(
                        {
                            "course_code":
                                course_code,

                            "unit":
                                unit,

                            "grade":
                                grade,

                            "point":
                                point,

                            "quality_point":
                                quality_point,
                        }
                    )


                if simulated_units == 0:

                    raise ValueError(
                        "Please add at least one course."
                    )


                semester_gpa = round(
                    simulated_quality_points
                    /
                    simulated_units,
                    2
                )


                new_total_units = (
                    current_total_units
                    +
                    simulated_units
                )


                new_total_quality_points = (
                    current_total_quality_points
                    +
                    simulated_quality_points
                )


                predicted_cgpa = round(
                    new_total_quality_points
                    /
                    new_total_units,
                    2
                )


                cgpa_change = round(
                    predicted_cgpa
                    -
                    current_cgpa,
                    2
                )


                result = {

                    "courses":
                        simulated_courses,

                    "semester_gpa":
                        semester_gpa,

                    "predicted_cgpa":
                        predicted_cgpa,

                    "cgpa_change":
                        cgpa_change,

                    "simulated_units":
                        simulated_units,

                    "simulated_quality_points":
                        simulated_quality_points,

                }


            except (
                TypeError,
                ValueError
            ) as error:

                result = {
                    "error":
                        str(error)
                }


    context = {

        "student":
            student,

        "current_cgpa":
            current_cgpa,

        "current_total_units":
            current_total_units,

        "current_total_quality_points":
            current_total_quality_points,

        "result":
            result,

    }


    return render(
        request,
        "calculator/grade_scenario_simulator.html",
        context
    )           

# =========================================================
# SERVICE WORKER
# =========================================================
def service_worker(request):

    service_worker_path = finders.find(
        "calculator/service-worker.js"
    )

    if not service_worker_path:

        raise Http404(
            "Service worker file was not found."
        )

    response = FileResponse(
        open(
            service_worker_path,
            "rb"
        ),
        content_type="application/javascript"
    )

    response[
        "Service-Worker-Allowed"
    ] = "/"

    return response    

@login_required
def cgpa_progress_chart(request):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    semesters = Semester.objects.filter(
        student=student
    ).order_by(
        "level",
        "semester"
    )


    labels = []

    semester_gpas = []

    cumulative_cgpas = []


    total_units = 0

    total_quality_points = 0


    for semester in semesters:

        courses = Course.objects.filter(
            semester=semester
        )


        semester_units = 0

        semester_quality_points = 0


        for course in courses:

            point = GRADE_POINTS.get(
                course.grade,
                0
            )


            quality_point = (
                course.course_unit
                *
                point
            )


            semester_units += (
                course.course_unit
            )


            semester_quality_points += (
                quality_point
            )


        if semester_units > 0:

            semester_gpa = round(
                semester_quality_points
                /
                semester_units,
                2
            )

        else:

            semester_gpa = 0


        total_units += (
            semester_units
        )


        total_quality_points += (
            semester_quality_points
        )


        if total_units > 0:

            cumulative_cgpa = round(
                total_quality_points
                /
                total_units,
                2
            )

        else:

            cumulative_cgpa = 0


        labels.append(
            f"{semester.level}L - {semester.semester}"
        )


        semester_gpas.append(
            semester_gpa
        )


        cumulative_cgpas.append(
            cumulative_cgpa
        )


    context = {

        "student":
            student,

        "labels":
            labels,

        "semester_gpas":
            semester_gpas,

        "cumulative_cgpas":
            cumulative_cgpas,

    }


    return render(
        request,
        "calculator/cgpa_progress_chart.html",
        context
    )    

# =========================================================
# ACADEMIC PERFORMANCE ANALYTICS
# =========================================================

@login_required
def academic_analytics(request):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    # =====================================================
    # GET STUDENT SEMESTERS
    # =====================================================

    semesters = Semester.objects.filter(
        student=student
    ).order_by(
        "level",
        "semester"
    )


    # =====================================================
    # ANALYTICS VARIABLES
    # =====================================================

    total_courses = 0

    total_units = 0

    total_quality_points = 0


    grade_counts = {

        "A": 0,

        "B": 0,

        "C": 0,

        "D": 0,

        "E": 0,

        "F": 0,

    }


    failed_courses = []

    weak_courses = []


    best_semester = None

    worst_semester = None


    best_gpa = None

    worst_gpa = None


    semester_performance = []


    # =====================================================
    # PROCESS SEMESTERS
    # =====================================================

    for semester in semesters:

        courses = Course.objects.filter(
            semester=semester
        )


        semester_units = 0

        semester_quality_points = 0

        semester_course_count = 0


        for course in courses:

            grade = (
                course.grade
                .strip()
                .upper()
            )


            point = GRADE_POINTS.get(
                grade,
                0
            )


            quality_point = (
                course.course_unit
                *
                point
            )


            total_courses += 1

            semester_course_count += 1


            total_units += (
                course.course_unit
            )


            total_quality_points += (
                quality_point
            )


            semester_units += (
                course.course_unit
            )


            semester_quality_points += (
                quality_point
            )


            # =============================================
            # GRADE COUNTS
            # =============================================

            if grade in grade_counts:

                grade_counts[grade] += 1


            # =============================================
            # FAILED COURSES
            # =============================================

            if grade == "F":

                failed_courses.append(
                    {
                        "course_code":
                            course.course_code,

                        "grade":
                            grade,

                        "unit":
                            course.course_unit,

                        "semester":
                            semester,
                    }
                )


            # =============================================
            # WEAK COURSES
            # D / E / F
            # =============================================

            if grade in [
                "D",
                "E",
                "F"
            ]:

                weak_courses.append(
                    {
                        "course_code":
                            course.course_code,

                        "grade":
                            grade,

                        "unit":
                            course.course_unit,

                        "semester":
                            semester,
                    }
                )


        # =================================================
        # SEMESTER GPA
        # =================================================

        if semester_units > 0:

            semester_gpa = round(
                semester_quality_points
                /
                semester_units,
                2
            )

        else:

            semester_gpa = 0


        semester_performance.append(
            {
                "semester":
                    semester,

                "gpa":
                    semester_gpa,

                "units":
                    semester_units,

                "course_count":
                    semester_course_count,
            }
        )


        # =================================================
        # BEST SEMESTER
        # =================================================

        if (
            best_gpa is None
            or
            semester_gpa > best_gpa
        ):

            best_gpa = semester_gpa

            best_semester = semester


        # =================================================
        # WORST SEMESTER
        # =================================================

        if (
            worst_gpa is None
            or
            semester_gpa < worst_gpa
        ):

            worst_gpa = semester_gpa

            worst_semester = semester


    # =====================================================
    # CURRENT CGPA
    # =====================================================

    if total_units > 0:

        current_cgpa = round(
            total_quality_points
            /
            total_units,
            2
        )

    else:

        current_cgpa = 0


    # =====================================================
    # MOST COMMON GRADE
    # =====================================================

    if total_courses > 0:

        most_common_grade = max(
            grade_counts,
            key=grade_counts.get
        )

    else:

        most_common_grade = "-"


    # =====================================================
    # ACADEMIC INSIGHTS
    # =====================================================

    insights = []


    if best_semester:

        insights.append(
            {
                "type":
                    "positive",

                "message":
                    (
                        "Your strongest semester was "
                        f"{best_semester.level} Level - "
                        f"{best_semester.semester} "
                        f"with a GPA of {best_gpa}."
                    )
            }
        )


    if failed_courses:

        insights.append(
            {
                "type":
                    "danger",

                "message":
                    (
                        f"You currently have "
                        f"{len(failed_courses)} failed "
                        f"course"
                        f"{'s' if len(failed_courses) != 1 else ''} "
                        f"in your academic record."
                    )
            }
        )


    if weak_courses:

        insights.append(
            {
                "type":
                    "warning",

                "message":
                    (
                        f"{len(weak_courses)} course"
                        f"{'s' if len(weak_courses) != 1 else ''} "
                        f"have grades D, E or F and may "
                        f"need extra attention."
                    )
            }
        )


    # =====================================================
    # PERFORMANCE TREND
    # =====================================================

    if len(
        semester_performance
    ) >= 2:

        previous_gpa = (
            semester_performance[-2][
                "gpa"
            ]
        )


        latest_gpa = (
            semester_performance[-1][
                "gpa"
            ]
        )


        if latest_gpa > previous_gpa:

            insights.append(
                {
                    "type":
                        "positive",

                    "message":
                        (
                            "Your latest semester GPA "
                            "improved compared with the "
                            "previous semester."
                        )
                }
            )


        elif latest_gpa < previous_gpa:

            insights.append(
                {
                    "type":
                        "warning",

                    "message":
                        (
                            "Your latest semester GPA "
                            "dropped compared with the "
                            "previous semester."
                        )
                }
            )


        else:

            insights.append(
                {
                    "type":
                        "neutral",

                    "message":
                        (
                            "Your latest semester GPA "
                            "remained unchanged."
                        )
                }
            )


    # =====================================================
    # CONTEXT
    # =====================================================

    context = {

        "student":
            student,

        "current_cgpa":
            current_cgpa,

        "total_courses":
            total_courses,

        "total_units":
            total_units,

        "total_quality_points":
            total_quality_points,

        "grade_counts":
            grade_counts,

        "failed_courses":
            failed_courses,

        "weak_courses":
            weak_courses,

        "best_semester":
            best_semester,

        "best_gpa":
            best_gpa,

        "worst_semester":
            worst_semester,

        "worst_gpa":
            worst_gpa,

        "most_common_grade":
            most_common_grade,

        "semester_performance":
            semester_performance,

        "insights":
            insights,

    }


    return render(
        request,
        "calculator/academic_analytics.html",
        context
    ) 

# =========================================================
# GRADUATION CGPA PREDICTOR
# =========================================================

@login_required
def graduation_cgpa_predictor(request):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    # =====================================================
    # CURRENT ACADEMIC TOTALS
    # =====================================================

    semesters = Semester.objects.filter(
        student=student
    )


    completed_units = 0

    total_quality_points = 0


    for semester in semesters:

        courses = Course.objects.filter(
            semester=semester
        )


        for course in courses:

            point = GRADE_POINTS.get(
                course.grade,
                0
            )


            completed_units += (
                course.course_unit
            )


            total_quality_points += (
                course.course_unit
                *
                point
            )


    if completed_units > 0:

        current_cgpa = round(
            total_quality_points
            /
            completed_units,
            2
        )

    else:

        current_cgpa = 0


    result = None


    # =====================================================
    # HANDLE FORM
    # =====================================================

    if request.method == "POST":

        try:

            target_cgpa = float(
                request.POST.get(
                    "target_cgpa",
                    ""
                )
            )


            remaining_units = int(
                request.POST.get(
                    "remaining_units",
                    ""
                )
            )


            # =============================================
            # VALIDATION
            # =============================================

            if (
                target_cgpa < 0
                or
                target_cgpa > 5
            ):

                raise ValueError(
                    "Target CGPA must be between 0.00 and 5.00."
                )


            if remaining_units <= 0:

                raise ValueError(
                    "Remaining units must be greater than zero."
                )


            # =============================================
            # REQUIRED GPA CALCULATION
            # =============================================

            final_total_units = (
                completed_units
                +
                remaining_units
            )


            required_final_quality_points = (
                target_cgpa
                *
                final_total_units
            )


            quality_points_needed = (
                required_final_quality_points
                -
                total_quality_points
            )


            required_average_gpa = (
                quality_points_needed
                /
                remaining_units
            )


            required_average_gpa = round(
                required_average_gpa,
                2
            )


            # =============================================
            # STATUS
            # =============================================

            if required_average_gpa > 5:

                status = "impossible"

                message = (
                    "This graduation target is not "
                    "mathematically achievable with "
                    "the remaining units."
                )


            elif required_average_gpa <= 0:

                status = "already_reached"

                message = (
                    "Your current academic record already "
                    "meets or exceeds this graduation target."
                )


            elif required_average_gpa >= 4.5:

                status = "very_difficult"

                message = (
                    "This target is achievable, but it "
                    "requires an excellent average GPA "
                    "across your remaining courses."
                )


            elif required_average_gpa >= 3.5:

                status = "challenging"

                message = (
                    "This target is achievable with strong "
                    "performance across your remaining units."
                )


            else:

                status = "achievable"

                message = (
                    "This target is currently achievable "
                    "with a realistic remaining GPA."
                )


            result = {

                "target_cgpa":
                    target_cgpa,

                "remaining_units":
                    remaining_units,

                "required_average_gpa":
                    required_average_gpa,

                "final_total_units":
                    final_total_units,

                "status":
                    status,

                "message":
                    message,

            }


        except (
            TypeError,
            ValueError
        ) as error:

            result = {

                "error":
                    str(error)

            }


    context = {

        "student":
            student,

        "current_cgpa":
            current_cgpa,

        "completed_units":
            completed_units,

        "total_quality_points":
            total_quality_points,

        "result":
            result,

    }


    return render(
        request,
        "calculator/graduation_cgpa_predictor.html",
        context
    )

# =========================================================
# CARRYOVER / RETAKE TRACKER
# =========================================================

@login_required
def retake_tracker(request):

    try:
        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    # =====================================================
    # FIND FAILED COURSES
    # =====================================================

    failed_courses = Course.objects.filter(
        semester__student=student,
        grade__iexact="F"
    ).select_related(
        "semester"
    )


    # =====================================================
    # ENSURE EACH FAILED COURSE HAS A RETAKE RECORD
    # =====================================================

    for course in failed_courses:

        CourseRetake.objects.get_or_create(
            student=student,
            original_course=course
        )


    # =====================================================
    # HANDLE STATUS / GRADE UPDATE
    # =====================================================

    if request.method == "POST":

        retake_id = request.POST.get(
            "retake_id"
        )

        status = request.POST.get(
            "status"
        )

        retake_grade = (
            request.POST.get(
                "retake_grade",
                ""
            )
            .strip()
            .upper()
        )

        notes = request.POST.get(
            "notes",
            ""
        ).strip()


        try:

            retake = CourseRetake.objects.get(
                id=retake_id,
                student=student
            )


            valid_statuses = {
                "pending",
                "in_progress",
                "completed",
            }


            if status not in valid_statuses:

                messages.error(
                    request,
                    "Invalid retake status."
                )

                return redirect(
                    "retake_tracker"
                )


            if retake_grade:

                valid_grades = {
                    "A",
                    "B",
                    "C",
                    "D",
                    "E",
                    "F",
                }


                if retake_grade not in valid_grades:

                    messages.error(
                        request,
                        "Invalid retake grade."
                    )

                    return redirect(
                        "retake_tracker"
                    )


            if (
                status == "completed"
                and
                not retake_grade
            ):

                messages.error(
                    request,
                    "Please enter the retake grade before marking the course as completed."
                )

                return redirect(
                    "retake_tracker"
                )


            retake.status = status

            retake.retake_grade = (
                retake_grade
                if retake_grade
                else None
            )

            retake.notes = notes

            retake.save()


            messages.success(
                request,
                "Retake information updated successfully."
            )


        except CourseRetake.DoesNotExist:

            messages.error(
                request,
                "Retake record not found."
            )


        return redirect(
            "retake_tracker"
        )


    # =====================================================
    # GET TRACKER RECORDS
    # =====================================================

    retakes = CourseRetake.objects.filter(
        student=student
    ).select_related(
        "original_course",
        "original_course__semester"
    ).order_by(
        "status",
        "original_course__semester__level",
        "original_course__course_code"
    )


    pending_count = retakes.filter(
        status="pending"
    ).count()


    in_progress_count = retakes.filter(
        status="in_progress"
    ).count()


    completed_count = retakes.filter(
        status="completed"
    ).count()


    context = {

        "student":
            student,

        "retakes":
            retakes,

        "failed_courses_count":
            failed_courses.count(),

        "pending_count":
            pending_count,

        "in_progress_count":
            in_progress_count,

        "completed_count":
            completed_count,

    }


    return render(
        request,
        "calculator/retake_tracker.html",
        context
    )         


# =========================================================
# DOWNLOAD ACADEMIC REPORT PDF
# =========================================================

@login_required
def download_academic_report(request):

    # =====================================================
    # GET STUDENT
    # =====================================================

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    # =====================================================
    # GET SEMESTERS
    # =====================================================

    semesters = Semester.objects.filter(
        student=student
    ).order_by(
        "level",
        "semester"
    )


    # =====================================================
    # CALCULATE OVERALL ACADEMIC TOTALS
    # =====================================================

    total_units = 0

    total_quality_points = 0

    total_courses = 0

    semester_results = []


    for semester in semesters:

        courses = Course.objects.filter(
            semester=semester
        )


        semester_units = 0

        semester_quality_points = 0

        course_rows = []


        for course in courses:

            grade = (
                course.grade
                .strip()
                .upper()
            )


            point = GRADE_POINTS.get(
                grade,
                0
            )


            quality_point = (
                course.course_unit
                *
                point
            )


            semester_units += (
                course.course_unit
            )


            semester_quality_points += (
                quality_point
            )


            total_units += (
                course.course_unit
            )


            total_quality_points += (
                quality_point
            )


            total_courses += 1


            course_rows.append(
                {
                    "course_code":
                        course.course_code,

                    "course_unit":
                        course.course_unit,

                    "grade":
                        grade,

                    "point":
                        point,

                    "quality_point":
                        quality_point,
                }
            )


        if semester_units > 0:

            semester_gpa = round(
                semester_quality_points
                /
                semester_units,
                2
            )

        else:

            semester_gpa = 0


        semester_results.append(
            {
                "semester":
                    semester,

                "courses":
                    course_rows,

                "units":
                    semester_units,

                "quality_points":
                    semester_quality_points,

                "gpa":
                    semester_gpa,
            }
        )


    # =====================================================
    # CURRENT CGPA
    # =====================================================

    if total_units > 0:

        cgpa = round(
            total_quality_points
            /
            total_units,
            2
        )

    else:

        cgpa = 0


    # =====================================================
    # CLASS OF DEGREE
    # =====================================================

    if cgpa >= 4.50:

        class_of_degree = (
            "First Class"
        )

    elif cgpa >= 3.50:

        class_of_degree = (
            "Second Class Upper"
        )

    elif cgpa >= 2.40:

        class_of_degree = (
            "Second Class Lower"
        )

    elif cgpa >= 1.50:

        class_of_degree = (
            "Third Class"
        )

    elif cgpa >= 1.00:

        class_of_degree = (
            "Pass"
        )

    else:

        class_of_degree = (
            "Fail"
        )


    # =====================================================
    # CREATE HTTP RESPONSE
    # =====================================================

    safe_matric = (
        str(student.matric_number)
        .replace("/", "-")
        .replace("\\", "-")
        .replace(" ", "_")
    )


    response = HttpResponse(
        content_type="application/pdf"
    )


    response[
        "Content-Disposition"
    ] = (
        f'attachment; '
        f'filename="A-DEVS_Academic_Report_{safe_matric}.pdf"'
    )


    # =====================================================
    # CREATE PDF DOCUMENT
    # =====================================================

    document = SimpleDocTemplate(

        response,

        pagesize=A4,

        rightMargin=1.4 * cm,

        leftMargin=1.4 * cm,

        topMargin=1.5 * cm,

        bottomMargin=1.5 * cm,

        title="A-DEVS Academic Report",

        author="A-DEVS CGPA Calculator",

    )


    elements = []


    # =====================================================
    # PDF STYLES
    # =====================================================

    styles = getSampleStyleSheet()


    title_style = ParagraphStyle(

        "ReportTitle",

        parent=styles["Title"],

        alignment=TA_CENTER,

        fontSize=20,

        leading=24,

        spaceAfter=8,

    )


    subtitle_style = ParagraphStyle(

        "Subtitle",

        parent=styles["Normal"],

        alignment=TA_CENTER,

        fontSize=10,

        textColor=colors.HexColor(
            "#666666"
        ),

        spaceAfter=18,

    )


    section_style = ParagraphStyle(

        "SectionHeading",

        parent=styles["Heading2"],

        fontSize=14,

        textColor=colors.HexColor(
            "#151c5a"
        ),

        spaceBefore=10,

        spaceAfter=10,

    )


    normal_style = styles[
        "Normal"
    ]


    # =====================================================
    # TITLE
    # =====================================================

    elements.append(
        Paragraph(
            "A-DEVS CGPA Calculator",
            title_style
        )
    )


    elements.append(
        Paragraph(
            "Student Academic Performance Report",
            subtitle_style
        )
    )


    # =====================================================
    # STUDENT INFORMATION
    # =====================================================

    elements.append(
        Paragraph(
            "Student Information",
            section_style
        )
    )


    student_data = [

        [
            "Student Name",
            str(
                student.name
                or "-"
            )
        ],

        [
            "Matric Number",
            str(
                student.matric_number
                or "-"
            )
        ],

        [
            "Department",
            str(
                student.department
                or "-"
            )
        ],

        [
            "University",
            str(
                student.university
                or "-"
            )
        ],

    ]


    student_table = Table(

        student_data,

        colWidths=[
            5 * cm,
            11 * cm,
        ]

    )


    student_table.setStyle(
        TableStyle(
            [

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor(
                        "#f1f3f5"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor(
                        "#222222"
                    )
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold"
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor(
                        "#dddddd"
                    )
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "PADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),

            ]
        )
    )


    elements.append(
        student_table
    )


    elements.append(
        Spacer(
            1,
            18
        )
    )


    # =====================================================
    # ACADEMIC SUMMARY
    # =====================================================

    elements.append(
        Paragraph(
            "Academic Summary",
            section_style
        )
    )


    summary_data = [

        [
            "Current CGPA",
            "Total Units",
            "Total Courses",
            "Class of Degree",
        ],

        [
            str(cgpa),

            str(total_units),

            str(total_courses),

            class_of_degree,
        ],

    ]


    summary_table = Table(

        summary_data,

        colWidths=[
            4 * cm,
            4 * cm,
            4 * cm,
            4 * cm,
        ]

    )


    summary_table.setStyle(
        TableStyle(
            [

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#151c5a"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "FONTNAME",
                    (0, 1),
                    (-1, 1),
                    "Helvetica-Bold"
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor(
                        "#cccccc"
                    )
                ),

                (
                    "PADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),

            ]
        )
    )


    elements.append(
        summary_table
    )


    elements.append(
        Spacer(
            1,
            20
        )
    )


    # =====================================================
    # SEMESTER RECORDS
    # =====================================================

    elements.append(
        Paragraph(
            "Semester Academic Records",
            section_style
        )
    )


    if semester_results:

        for semester_result in semester_results:

            semester = (
                semester_result[
                    "semester"
                ]
            )


            semester_title = (
                f"{semester.level} Level - "
                f"{semester.semester}"
            )


            elements.append(
                Paragraph(
                    semester_title,
                    styles[
                        "Heading3"
                    ]
                )
            )


            elements.append(
                Paragraph(
                    (
                        f"GPA: "
                        f"<b>{semester_result['gpa']}</b>"
                        f" &nbsp;&nbsp; "
                        f"Units: "
                        f"<b>{semester_result['units']}</b>"
                    ),
                    normal_style
                )
            )


            elements.append(
                Spacer(
                    1,
                    8
                )
            )


            course_table_data = [

                [
                    "Course",
                    "Units",
                    "Grade",
                    "Point",
                    "Quality Points",
                ]

            ]


            for course in semester_result[
                "courses"
            ]:

                course_table_data.append(
                    [
                        str(
                            course[
                                "course_code"
                            ]
                        ),

                        str(
                            course[
                                "course_unit"
                            ]
                        ),

                        str(
                            course[
                                "grade"
                            ]
                        ),

                        str(
                            course[
                                "point"
                            ]
                        ),

                        str(
                            course[
                                "quality_point"
                            ]
                        ),
                    ]
                )


            if len(
                course_table_data
            ) == 1:

                course_table_data.append(
                    [
                        "No courses recorded",
                        "-",
                        "-",
                        "-",
                        "-",
                    ]
                )


            course_table = Table(

                course_table_data,

                repeatRows=1,

                colWidths=[
                    4.5 * cm,
                    2.5 * cm,
                    2.5 * cm,
                    2.5 * cm,
                    4 * cm,
                ]

            )


            course_table.setStyle(
                TableStyle(
                    [

                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            colors.HexColor(
                                "#0d6efd"
                            )
                        ),

                        (
                            "TEXTCOLOR",
                            (0, 0),
                            (-1, 0),
                            colors.white
                        ),

                        (
                            "FONTNAME",
                            (0, 0),
                            (-1, 0),
                            "Helvetica-Bold"
                        ),

                        (
                            "ALIGN",
                            (1, 0),
                            (-1, -1),
                            "CENTER"
                        ),

                        (
                            "GRID",
                            (0, 0),
                            (-1, -1),
                            0.5,
                            colors.HexColor(
                                "#dddddd"
                            )
                        ),

                        (
                            "PADDING",
                            (0, 0),
                            (-1, -1),
                            7
                        ),

                    ]
                )
            )


            elements.append(
                course_table
            )


            elements.append(
                Spacer(
                    1,
                    20
                )
            )

    else:

        elements.append(
            Paragraph(
                "No academic records have been added yet.",
                normal_style
            )
        )


    # =====================================================
    # FOOTER NOTE
    # =====================================================

    elements.append(
        Spacer(
            1,
            20
        )
    )


    elements.append(
        Paragraph(
            (
                "Generated by A-DEVS CGPA Calculator. "
                "This report is based on academic information "
                "entered by the student and is not an official "
                "university transcript."
            ),
            subtitle_style
        )
    )


    # =====================================================
    # BUILD PDF
    # =====================================================

    document.build(
        elements
    )


    return response     


# =========================================================
# SMART ACADEMIC ADVISOR
# =========================================================

@login_required
def smart_academic_advisor(request):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    # =====================================================
    # GET STUDENT SEMESTERS
    # =====================================================

    semesters = Semester.objects.filter(
        student=student
    ).order_by(
        "level",
        "semester"
    )


    total_units = 0

    total_quality_points = 0

    failed_courses = []

    semester_performance = []


    # =====================================================
    # PROCESS ACADEMIC RECORD
    # =====================================================

    for semester in semesters:

        courses = Course.objects.filter(
            semester=semester
        )


        semester_units = 0

        semester_quality_points = 0


        for course in courses:

            grade = (
                course.grade
                .strip()
                .upper()
            )


            point = GRADE_POINTS.get(
                grade,
                0
            )


            quality_point = (
                course.course_unit
                *
                point
            )


            semester_units += (
                course.course_unit
            )


            semester_quality_points += (
                quality_point
            )


            total_units += (
                course.course_unit
            )


            total_quality_points += (
                quality_point
            )


            if grade == "F":

                failed_courses.append(
                    course
                )


        if semester_units > 0:

            semester_gpa = round(
                semester_quality_points
                /
                semester_units,
                2
            )

        else:

            semester_gpa = 0


        semester_performance.append(
            {
                "semester":
                    semester,

                "gpa":
                    semester_gpa,
            }
        )


    # =====================================================
    # CURRENT CGPA
    # =====================================================

    if total_units > 0:

        current_cgpa = round(
            total_quality_points
            /
            total_units,
            2
        )

    else:

        current_cgpa = 0


    # =====================================================
    # CLASS OF DEGREE
    # =====================================================

    if current_cgpa >= 4.50:

        class_of_degree = (
            "First Class"
        )

    elif current_cgpa >= 3.50:

        class_of_degree = (
            "Second Class Upper"
        )

    elif current_cgpa >= 2.40:

        class_of_degree = (
            "Second Class Lower"
        )

    elif current_cgpa >= 1.50:

        class_of_degree = (
            "Third Class"
        )

    elif current_cgpa >= 1.00:

        class_of_degree = (
            "Pass"
        )

    else:

        class_of_degree = (
            "Fail"
        )


    # =====================================================
    # ADVICE LIST
    # =====================================================

    advice = []


    # =====================================================
    # CGPA BASED ADVICE
    # =====================================================

    if current_cgpa >= 4.50:

        advice.append(
            {
                "type":
                    "success",

                "icon":
                    "🏆",

                "title":
                    "Excellent Academic Standing",

                "message":
                    (
                        "Your CGPA is currently in the "
                        "First Class range. Maintain strong "
                        "performance and avoid unnecessary "
                        "grade drops."
                    ),
            }
        )


    elif current_cgpa >= 3.50:

        advice.append(
            {
                "type":
                    "success",

                "icon":
                    "📈",

                "title":
                    "Strong Academic Position",

                "message":
                    (
                        "You are currently in the "
                        "Second Class Upper range. "
                        "A few strong semesters could move "
                        "you closer to First Class."
                    ),
            }
        )


    elif current_cgpa >= 2.40:

        advice.append(
            {
                "type":
                    "warning",

                "icon":
                    "🎯",

                "title":
                    "Improvement Opportunity",

                "message":
                    (
                        "Your CGPA is currently in the "
                        "Second Class Lower range. "
                        "Focus on higher-unit courses and aim "
                        "for more A and B grades."
                    ),
            }
        )


    elif current_cgpa >= 1.50:

        advice.append(
            {
                "type":
                    "danger",

                "icon":
                    "⚠️",

                "title":
                    "Academic Risk",

                "message":
                    (
                        "Your CGPA is currently in the "
                        "Third Class range. Prioritize difficult "
                        "courses early and use the Goal Planner "
                        "before the next semester."
                    ),
            }
        )


    else:

        advice.append(
            {
                "type":
                    "danger",

                "icon":
                    "🚨",

                "title":
                    "Urgent Academic Attention Needed",

                "message":
                    (
                        "Your current CGPA is very low. "
                        "Consider speaking with an academic adviser, "
                        "reviewing failed courses and setting realistic "
                        "semester targets."
                    ),
            }
        )


    # =====================================================
    # FAILED COURSE ADVICE
    # =====================================================

    if failed_courses:

        failed_count = len(
            failed_courses
        )


        advice.append(
            {
                "type":
                    "danger",

                "icon":
                    "🔁",

                "title":
                    "Carryover Courses Detected",

                "message":
                    (
                        f"You currently have {failed_count} "
                        f"failed course"
                        f"{'s' if failed_count != 1 else ''}. "
                        f"Use the Carryover / Retake Tracker "
                        f"to monitor them."
                    ),
            }
        )


    else:

        if total_units > 0:

            advice.append(
                {
                    "type":
                        "success",

                    "icon":
                        "✅",

                    "title":
                        "No Failed Courses",

                    "message":
                        (
                            "No F grades were found in your "
                            "academic record. Keep maintaining "
                            "this consistency."
                        ),
                }
            )


    # =====================================================
    # SEMESTER TREND ADVICE
    # =====================================================

    if len(
        semester_performance
    ) >= 2:

        previous_gpa = (
            semester_performance[-2][
                "gpa"
            ]
        )


        latest_gpa = (
            semester_performance[-1][
                "gpa"
            ]
        )


        if latest_gpa > previous_gpa:

            difference = round(
                latest_gpa
                -
                previous_gpa,
                2
            )


            advice.append(
                {
                    "type":
                        "success",

                    "icon":
                        "📈",

                    "title":
                        "Semester Performance Improved",

                    "message":
                        (
                            f"Your latest GPA improved by "
                            f"{difference} compared with the "
                            f"previous semester."
                        ),
                }
            )


        elif latest_gpa < previous_gpa:

            difference = round(
                previous_gpa
                -
                latest_gpa,
                2
            )


            advice.append(
                {
                    "type":
                        "warning",

                    "icon":
                        "📉",

                    "title":
                        "Semester GPA Declined",

                    "message":
                        (
                            f"Your latest semester GPA dropped "
                            f"by {difference}. Review what changed "
                            f"and consider using the Grade Simulator "
                            f"to plan your next semester."
                        ),
                }
            )


        else:

            advice.append(
                {
                    "type":
                        "neutral",

                    "icon":
                        "➖",

                    "title":
                        "Stable Performance",

                    "message":
                        (
                            "Your latest semester GPA is the same "
                            "as the previous semester. A stronger "
                            "next semester can help improve your CGPA."
                        ),
                }
            )


    # =====================================================
    # HIGH UNIT ADVICE
    # =====================================================

    if total_units >= 80:

        advice.append(
            {
                "type":
                    "info",

                "icon":
                    "🎓",

                "title":
                    "CGPA Changes Become Slower",

                "message":
                    (
                        "You already have many completed units. "
                        "As total units increase, changing your CGPA "
                        "becomes harder, so consistent high GPAs "
                        "matter more."
                    ),
            }
        )


    # =====================================================
    # NO RECORD YET
    # =====================================================

    if total_units == 0:

        advice = [

            {
                "type":
                    "info",

                "icon":
                    "📚",

                "title":
                    "Start Building Your Academic Record",

                "message":
                    (
                        "You do not have semester results yet. "
                        "Add your first semester to receive "
                        "personalized academic advice."
                    ),
            }

        ]


    context = {

        "student":
            student,

        "current_cgpa":
            current_cgpa,

        "class_of_degree":
            class_of_degree,

        "total_units":
            total_units,

        "failed_courses_count":
            len(
                failed_courses
            ),

        "semester_count":
            len(
                semester_performance
            ),

        "advice":
            advice,

    }


    return render(
        request,
        "calculator/smart_academic_advisor.html",
        context
    )    


# =========================================================
# ACADEMIC PLANNER
# =========================================================

@login_required
def academic_planner(request):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )

    create_academic_task_notifications(
        student
    )    


    tasks = AcademicTask.objects.filter(
        student=student
    ).order_by(
        "is_completed",
        "due_date",
        "due_time"
    )


    upcoming_tasks = tasks.filter(
        is_completed=False
    )


    completed_tasks = tasks.filter(
        is_completed=True
    )


    context = {

        "student":
            student,

        "upcoming_tasks":
            upcoming_tasks,

        "completed_tasks":
            completed_tasks,

        "upcoming_count":
            upcoming_tasks.count(),

        "completed_count":
            completed_tasks.count(),

    }


    return render(
        request,
        "calculator/academic_planner.html",
        context
    )

def about(request):
    return render(request, "calculator/about.html")    

# =========================================================
# ADD ACADEMIC TASK
# =========================================================

@login_required
def add_academic_task(request):

    try:
        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    if request.method == "POST":

        title = request.POST.get(
            "title",
            ""
        ).strip()

        course_code = request.POST.get(
            "course_code",
            ""
        ).strip().upper()

        task_type = request.POST.get(
            "task_type",
            ""
        ).strip()

        priority = request.POST.get(
            "priority",
            ""
        ).strip()

        due_date = request.POST.get(
            "due_date",
            ""
        ).strip()

        due_time = request.POST.get(
            "due_time",
            ""
        ).strip()

        description = request.POST.get(
            "description",
            ""
        ).strip()


        # =================================================
        # VALIDATION
        # =================================================

        if not title:

            messages.error(
                request,
                "Please enter a task title."
            )

            return redirect(
                "add_academic_task"
            )


        valid_task_types = {
            "assignment",
            "test",
            "project",
            "presentation",
            "study",
            "exam",
            "registration",
            "other",
        }


        if task_type not in valid_task_types:

            messages.error(
                request,
                "Please select a valid task type."
            )

            return redirect(
                "add_academic_task"
            )


        valid_priorities = {
            "low",
            "medium",
            "high",
        }


        if priority not in valid_priorities:

            messages.error(
                request,
                "Please select a valid priority."
            )

            return redirect(
                "add_academic_task"
            )


        if not due_date:

            messages.error(
                request,
                "Please select a due date."
            )

            return redirect(
                "add_academic_task"
            )


        # =================================================
        # CREATE TASK
        # =================================================

        AcademicTask.objects.create(

            student=student,

            title=title,

            course_code=course_code,

            task_type=task_type,

            priority=priority,

            due_date=due_date,

            due_time=(
                due_time
                if due_time
                else None
            ),

            description=description,

            is_completed=False,

        )


        messages.success(
            request,
            "Academic task added successfully."
        )


        return redirect(
            "academic_planner"
        )


    context = {
        "student": student,
    }


    return render(
        request,
        "calculator/add_academic_task.html",
        context
    )    


# =========================================================
# ADD ACADEMIC TASK
# =========================================================

@login_required
def add_academic_task(request):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    if request.method == "POST":

        title = request.POST.get(
            "title",
            ""
        ).strip()


        course_code = request.POST.get(
            "course_code",
            ""
        ).strip().upper()


        task_type = request.POST.get(
            "task_type",
            "assignment"
        )


        priority = request.POST.get(
            "priority",
            "medium"
        )


        due_date = request.POST.get(
            "due_date",
            ""
        )


        due_time = request.POST.get(
            "due_time",
            ""
        )


        description = request.POST.get(
            "description",
            ""
        ).strip()


        if not title:

            messages.error(
                request,
                "Please enter a task title."
            )

            return redirect(
                "add_academic_task"
            )


        if not due_date:

            messages.error(
                request,
                "Please select a due date."
            )

            return redirect(
                "add_academic_task"
            )


        AcademicTask.objects.create(

            student=student,

            title=title,

            course_code=course_code,

            task_type=task_type,

            priority=priority,

            due_date=due_date,

            due_time=(
                due_time
                if due_time
                else None
            ),

            description=description,

        )


        messages.success(
            request,
            "Academic task added successfully."
        )


        return redirect(
            "academic_planner"
        )


    return render(
        request,
        "calculator/add_academic_task.html",
        {
            "student":
                student
        }
    )


# =========================================================
# COMPLETE ACADEMIC TASK
# =========================================================

@login_required
def complete_academic_task(
    request,
    task_id
):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    try:

        task = AcademicTask.objects.get(
            id=task_id,
            student=student
        )

    except AcademicTask.DoesNotExist:

        messages.error(
            request,
            "Task not found."
        )

        return redirect(
            "academic_planner"
        )


    task.is_completed = True

    task.save()


    messages.success(
        request,
        "Task marked as completed."
    )


    return redirect(
        "academic_planner"
    )


# =========================================================
# DELETE ACADEMIC TASK
# =========================================================

@login_required
def delete_academic_task(
    request,
    task_id
):

    try:

        student = Student.objects.get(
            user=request.user
        )

    except Student.DoesNotExist:

        messages.error(
            request,
            "Student profile not found."
        )

        return redirect(
            "login"
        )


    try:

        task = AcademicTask.objects.get(
            id=task_id,
            student=student
        )

    except AcademicTask.DoesNotExist:

        messages.error(
            request,
            "Task not found."
        )

        return redirect(
            "academic_planner"
        )


    task.delete()


    messages.success(
        request,
        "Task deleted successfully."
    )


    return redirect(
        "academic_planner"
    )  

def about(request):

    student = None

    if request.user.is_authenticated:
        try:
            student = Student.objects.get(
                user=request.user
            )
        except Student.DoesNotExist:
            student = None

    return render(
        request,
        "calculator/about.html",
        {
            "student": student
        }
    )  

def contact(request):

    student = None

    if request.user.is_authenticated:
        try:
            student = Student.objects.get(
                user=request.user
            )
        except Student.DoesNotExist:
            student = None

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        subject = request.POST.get(
            "subject",
            ""
        ).strip()

        message_text = request.POST.get(
            "message",
            ""
        ).strip()

        if (
            name
            and email
            and subject
            and message_text
        ):

            ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message_text
            )

            messages.success(
                request,
                "Thank you. Your message has been received."
            )

            return redirect(
                "contact"
            )

        messages.error(
            request,
            "Please complete all fields."
        )

    return render(
        request,
        "calculator/contact.html",
        {
            "student": student
        }
    )

def faq(request):

    student = None

    if request.user.is_authenticated:
        try:
            student = Student.objects.get(
                user=request.user
            )
        except Student.DoesNotExist:
            student = None

    return render(
        request,
        "calculator/faq.html",
        {
            "student": student
        }
    )

def privacy(request):

    student = None

    if request.user.is_authenticated:
        try:
            student = Student.objects.get(
                user=request.user
            )
        except Student.DoesNotExist:
            student = None

    return render(
        request,
        "calculator/privacy.html",
        {
            "student": student
        }
    )

def terms(request):

    student = None

    if request.user.is_authenticated:
        try:
            student = Student.objects.get(
                user=request.user
            )
        except Student.DoesNotExist:
            student = None

    return render(
        request,
        "calculator/terms.html",
        {
            "student": student
        }
    )        

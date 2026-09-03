from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from calculator import views


urlpatterns = [

    # =====================================================
    # ADMIN
    # =====================================================

    path(
        "admin/",
        admin.site.urls
    ),


    # =====================================================
    # HOME / CGPA CALCULATOR
    # =====================================================

    path(
        "",
        views.home,
        name="home"
    ),


    # =====================================================
    # STUDENT REGISTRATION
    # =====================================================

    path(
        "register/",
        views.register,
        name="register"
    ),


    # =====================================================
    # STUDENT LOGIN
    # =====================================================

    path(
        "login/",
        views.login_view,
        name="login"
    ),


    # =====================================================
    # STUDENT LOGOUT
    # =====================================================

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),


    # =====================================================
    # STUDENT PROFILE
    # =====================================================

    path(
        "profile/",
        views.profile,
        name="profile"
    ),


    # =====================================================
    # STUDENT DASHBOARD
    # =====================================================

    path(
        "dashboard/<path:matric_number>/",
        views.dashboard,
        name="dashboard"
    ),

    # =====================================================
    # CGPA GOAL PLANNER
    # =====================================================

    path(
    "cgpa-goal-planner/",
    views.cgpa_goal_planner,
    name="cgpa_goal_planner"
    ),

    # =====================================================
    # GRADE SCENARIO SIMULATOR
    # =====================================================

path(
    "grade-simulator/",
    views.grade_scenario_simulator,
    name="grade_scenario_simulator"
),

path(
    "cgpa-progress/",
    views.cgpa_progress_chart,
    name="cgpa_progress_chart"
),

# =====================================================
# GRADUATION CGPA PREDICTOR
# =====================================================

path(
    "graduation-predictor/",
    views.graduation_cgpa_predictor,
    name="graduation_cgpa_predictor"
),

# =====================================================
# CARRYOVER / RETAKE TRACKER
# =====================================================

path(
    "retake-tracker/",
    views.retake_tracker,
    name="retake_tracker"
),

# =====================================================
# ACADEMIC REPORT PDF
# =====================================================

path(
    "download-academic-report/",
    views.download_academic_report,
    name="download_academic_report"
),

# =====================================================
# SMART ACADEMIC ADVISOR
# =====================================================

path(
    "academic-advisor/",
    views.smart_academic_advisor,
    name="smart_academic_advisor"
),

# =====================================================
# ACADEMIC PLANNER
# =====================================================

path(
    "academic-planner/",
    views.academic_planner,
    name="academic_planner"
),

path(
    "academic-planner/add/",
    views.add_academic_task,
    name="add_academic_task"
),

path(
    "academic-planner/complete/<int:task_id>/",
    views.complete_academic_task,
    name="complete_academic_task"
),

path(
    "academic-planner/delete/<int:task_id>/",
    views.delete_academic_task,
    name="delete_academic_task"
),

# =====================================================
# ACADEMIC ANALYTICS
# =====================================================

path(
    "academic-analytics/",
    views.academic_analytics,
    name="academic_analytics"
),


    # =====================================================
    # ACADEMIC RECORD
    # =====================================================

    path(
        "record/<path:matric_number>/",
        views.academic_record,
        name="academic_record"
    ),


    # =====================================================
    # ADD SEMESTER
    # =====================================================

    path(
        "add-semester/<path:matric_number>/",
        views.add_semester,
        name="add_semester"
    ),


    # =====================================================
    # DELETE SEMESTER
    # =====================================================

    path(
        "delete-semester/<int:semester_id>/",
        views.delete_semester,
        name="delete_semester"
    ),


    # =====================================================
    # EDIT COURSE
    # =====================================================

    path(
        "edit-course/<int:course_id>/",
        views.edit_course,
        name="edit_course"
    ),


    # =====================================================
    # DELETE COURSE
    # =====================================================

    path(
        "delete-course/<int:course_id>/",
        views.delete_course,
        name="delete_course"
    ),


    # =====================================================
    # PASSWORD RECOVERY
    # =====================================================
    # Student enters their email address here.
    # Django sends the password reset email.

   path(
    "password-reset/",
    auth_views.PasswordResetView.as_view(
        template_name="calculator/password_reset.html",
        email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt",
    ),
    name="password_reset"
),


    # =====================================================
    # PASSWORD RESET EMAIL SENT
    # =====================================================

    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="calculator/password_reset_done.html"
        ),
        name="password_reset_done"
    ),


    # =====================================================
    # CREATE NEW PASSWORD
    # =====================================================

    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="calculator/password_reset_confirm.html"
        ),
        name="password_reset_confirm"
    ),


    # =====================================================
    # PASSWORD RESET COMPLETE
    # =====================================================

    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="calculator/password_reset_complete.html"
        ),
        name="password_reset_complete"
    ),

    path(
    "notifications/",
    views.notifications_view,
    name="notifications"
),

path(
    "notifications/read/<int:notification_id>/",
    views.mark_notification_read,
    name="mark_notification_read"
),

path(
    "notifications/read-all/",
    views.mark_all_notifications_read,
    name="mark_all_notifications_read"
),

path(
    "notifications/delete/<int:notification_id>/",
    views.delete_notification,
    name="delete_notification"
),

path(
    "exams/",
    views.exam_reminders,
    name="exam_reminders"
),

path(
    "exams/add/",
    views.add_exam_reminder,
    name="add_exam_reminder"
),

path(
    "exams/complete/<int:exam_id>/",
    views.complete_exam,
    name="complete_exam"
),

path(
    "exams/delete/<int:exam_id>/",
    views.delete_exam_reminder,
    name="delete_exam_reminder"
),

path(
    "offline/",
    views.offline_view,
    name="offline"
),

path(
    "service-worker.js",
    views.service_worker,
    name="service_worker"
),

path(
    "sync-offline-result/",
    views.sync_offline_result,
    name="sync_offline_result"
),

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
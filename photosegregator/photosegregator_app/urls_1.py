# photosegregator_app/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # ── Frontend - Event Manager ──────────────────────
    path("", views.event_manager_home, name="event_manager_home"),
    
    # ── Event Pages ───────────────────────────────────
    path("event/<str:event_code>/", views.event_guest_page, name="event_guest"),
    path("event/<str:event_code>/details/", views.event_details, name="event_details"),
    
    # ── API: Event Creation ───────────────────────────
    path("api/event/create/", views.api_create_event, name="create_event"),
    
    # ── API: Event-based Photo Finding ────────────────
    path("api/event/<str:event_code>/find-my-photos/", 
         views.api_find_my_photos_event, name="find_my_photos_event"),
    
    path("api/event/<str:event_code>/photo/<str:filename>/", 
         views.api_serve_photo_event, name="serve_photo_event"),
    
    path("api/event/<str:event_code>/download/<str:filename>/", 
         views.api_download_photo_event, name="download_photo_event"),
    
    path("api/event/<str:event_code>/download-all/", 
         views.api_download_all_photos_event, name="download_all_event"),
    
    # ── Old endpoints (optional, for backwards compatibility) ──
    # path("old-admin/", views.admin_dashboard, name="admin_dashboard"),
]
from django.urls import path
from . import views

app_name = 'photosegregator_app'

urlpatterns = [
    # ════════════════════════════════════════════════════════════════
    # EVENT MANAGER PAGES
    # ════════════════════════════════════════════════════════════════
    path('', views.event_manager_home, name='event_manager_home'),
    path('event/<str:event_code>/', views.event_details, name='event_details'),
    path('event/<str:event_code>/guest/', views.event_guest_page, name='event_guest_page'),
    
    # ════════════════════════════════════════════════════════════════
    # API: EVENT MANAGEMENT
    # ════════════════════════════════════════════════════════════════
    path('api/event/create/', views.api_create_event, name='api_create_event'),
    
    # ════════════════════════════════════════════════════════════════
    # API: PHOTO OPERATIONS
    # ════════════════════════════════════════════════════════════════
    path('api/event/<str:event_code>/find-my-photos/', views.api_find_my_photos_event, name='api_find_my_photos_event'),
    path('api/event/<str:event_code>/photo/<str:filename>/', views.api_serve_photo_event, name='api_serve_photo_event'),
    path('api/event/<str:event_code>/download/<str:filename>/', views.api_download_photo_event, name='api_download_photo_event'),
    path('api/event/<str:event_code>/download-all/', views.api_download_all_photos_event, name='api_download_all_photos_event'),
]
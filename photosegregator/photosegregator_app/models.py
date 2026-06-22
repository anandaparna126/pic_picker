from django.db import models
import string
import random

class Event(models.Model):
    """Event session for guests to upload selfies and find photos"""
    event_code = models.CharField(max_length=8, unique=True, db_index=True)
    event_name = models.CharField(max_length=255)
    manager_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event_name} ({self.event_code})"
    
    def save(self, *args, **kwargs):
        if not self.event_code:
            chars = string.ascii_uppercase + string.digits
            self.event_code = ''.join(random.choice(chars) for _ in range(8))
        super().save(*args, **kwargs)
    
    @property
    def gallery_path(self):
        """Event-specific gallery folder"""
        return f"gallery_images/{self.event_code}"
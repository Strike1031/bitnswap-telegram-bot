from django.db import models

class UserInfo(models.Model):
    user_id = models.IntegerField(unique=True)
    user_name = models.CharField(max_length=255)
    user_score = models.IntegerField(default=0)
    user_login_timestamp = models.DateTimeField()
    

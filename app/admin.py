from django.contrib import admin
from .models import UserInfo


class PersonAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'user_name', 'user_score', 'user_login_timestamp')


admin.site.register(UserInfo, PersonAdmin)

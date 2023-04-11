from django.contrib import admin

# Register your models here.

from .models import Chain, Altruist, AltruistServingLog

admin.site.register(Chain)
admin.site.register(Altruist)
admin.site.register(AltruistServingLog)
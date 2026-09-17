from django.contrib import admin

from .models import Category, Gig, GigSkill

admin.site.register(Category)
admin.site.register(Gig)
admin.site.register(GigSkill)

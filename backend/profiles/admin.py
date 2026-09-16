from django.contrib import admin

from .models import ClientProfile, FreelancerProfile, PortfolioItem, Skill

admin.site.register(Skill)
admin.site.register(ClientProfile)
admin.site.register(FreelancerProfile)
admin.site.register(PortfolioItem)

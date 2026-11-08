from django.contrib import admin

from .models import ClientProfile, FreelancerProfile, PortfolioItem, Skill

admin.site.register(Skill)
admin.site.register(ClientProfile)


@admin.register(FreelancerProfile)
class FreelancerProfileAdmin(admin.ModelAdmin):
    # ID details are only for the verification queue in the admin area, which logs every decision.
    exclude = ['id_number', 'id_document']


admin.site.register(PortfolioItem)

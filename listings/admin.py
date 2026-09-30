from django.contrib import admin

from listings.models import Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ["title", "type", "price", "bedrooms", "agent_id", "location_name", "created_at"]
    list_filter = ["type", "bedrooms", "agent_id", "created_at"]
    search_fields = ["title", "description", "agent_id", "location_name"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]

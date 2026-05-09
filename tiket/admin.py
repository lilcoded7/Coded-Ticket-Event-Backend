from django.contrib import admin
from .models import *


@admin.register(CodedProperty)
class CodedPropertyAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        if CodedProperty.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "start_time", "user")

    def has_add_permission(self, request):
        if Event.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_code",
        "category",
        "price",
        "is_perchased",
        "is_used",
        "is_verified",  # This makes it show in the table list
    )
    list_filter = ("is_perchased", "is_used", "category", "is_verified")
    search_fields = ("ticket_code", "name")
    readonly_fields = ("ticket_code", "qr_code", "purchased_at")

    fieldsets = (
        ("Event Details", {"fields": ("event", "category", "name", "price")}),
        (
            "Status",
            {
                "fields": (
                    "is_perchased",
                    "is_used",
                    "is_verified",
                    "quantity_available",
                )  # Added is_verified here
            },
        ),
        (
            "Technical",
            {
                "fields": (
                    "ticket_code",
                    "qr_code",
                    "ticket_image",
                    "purchased_at",
                )  # Added ticket_image here
            },
        ),
    )


@admin.register(Benefit)
class BenefitAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    filter_horizontal = ("category",)


admin.site.register(PayoutAccount)
admin.site.register(Transaction)

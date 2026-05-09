from django.urls import path
from .views import *

urlpatterns = [
    path(
        "bulk/create/tickets/",
        TicketBulkCreateView.as_view(),
        name="bulk_create_tickets",
    ),
    path(
        "tickets/available/",
        AvailableTicketListView.as_view(),
        name="available_tickets",
    ),
    path(
        "tickets/purchase/<uuid:ticket_id>/",
        TicketPurchaseView.as_view(),
        name="purchase-ticket",
    ),
    path("inventory/", TicketInventoryView.as_view(), name="inventory_list"),
    path("metrics/", DashboardMetricsView.as_view(), name="dashboard_metrics"),
    path(
        "create/list/category/",
        CreateCategorySerializer.as_view(),
        name="create_category_list",
    ),
    path("accounts/login/", LoginAccountAPIView.as_view(), name="login_account"),
    path("transactions/", TransactionListView.as_view(), name="transaction-list"),
    path(
        "withdrawal/request/",
        WithdrawalRequestView.as_view(),
        name="withdrawal-request",
    ),
    path(
        "payout/account/",
        PayoutAccountDetailView.as_view(),
        name="payout-account-detail",
    ),
    path("verify/ticket/", VerifyTicketView.as_view(), name="verify_ticket"),
    path("purchase/ticket/", TicketPurchaseView.as_view(), name="purchase_ticket"),
    path('verify/transaction/<str:reference>/', TransactionVerifyView.as_view(), name='verify_transaction'),
    path('retrieve/ticket/', RetrieveTicketView.as_view(), name='retrieve_ticket')
]

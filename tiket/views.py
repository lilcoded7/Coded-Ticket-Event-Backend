from rest_framework import generics, status
from rest_framework.response import Response
from .serializers import *
from .models import *

from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.views import APIView
from tiket.pay import PaymentGateWay
from decimal import Decimal




class TicketBulkCreateView(generics.GenericAPIView):
    serializer_class = BulkTicketCreateSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            tickets = serializer.save()
            return Response(
                {"message": f"Successfully created {len(tickets)} tickets."},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


class AvailableTicketListView(generics.ListAPIView):
    serializer_class = TicketListSerializer

    def get_queryset(self):
       
        return Ticket.objects.filter(
            is_perchased=False, 
            is_used=False
        ).select_related('category').prefetch_related('category__benefit_set')

    def get(self, request):
        tickets = self.get_queryset()
        event = Event.objects.first()
        
        return Response({
            "event": EventSerializer(event).data if event else None,
            "tickets": self.serializer_class(tickets, many=True).data
        })


# Dashboard

class TicketInventoryView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DashboardTicketSerializer

    def get(self, request):
        queryset = Ticket.objects.all().select_related('event', 'category')
        status_param = request.query_params.get('filter')

        if status_param == 'sold':
            queryset = queryset.filter(is_perchased=True)
        elif status_param == 'unsold':
            queryset = queryset.filter(is_perchased=False)

        serializer = self.serializer_class(queryset, many=True)
        event = Event.objects.first()
        event_serializer = DashboardEventSerializer(event)

        return Response({
            "event": event_serializer.data,
            "tickets": serializer.data
        })

class DashboardMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        current_date = timezone.now().date()
        
        total_revenue = Ticket.objects.filter(is_perchased=True).aggregate(total=Sum('price'))['total'] or 0
        today_sales = Ticket.objects.filter(
            is_perchased=True, 
            updated_at__date=current_date
        ).aggregate(total=Sum('price'))['total'] or 0
        
        sold_count = Ticket.objects.filter(is_perchased=True).count()
        unsold_count = Ticket.objects.filter(is_perchased=False).count()

        return Response({
            "total_revenue": total_revenue,
            "todays_sales": today_sales,
            "sold_tickets": sold_count,
            "unsold_stock": unsold_count,
            "current_date": current_date,
            "balance": Event.objects.first().balance or 0.00
        })
    

class CreateCategorySerializer(APIView):

    def get(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)
    

class LoginAccountAPIView(generics.GenericAPIView):
    serializer_class = LoginUserSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)
    

class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Transaction.objects.all().order_by('-created_at')
        txn_type = self.request.query_params.get('type')
        txn_status = self.request.query_params.get('status')

        if txn_type:
            queryset = queryset.filter(transaction_type__iexact=txn_type)
        if txn_status:
            queryset = queryset.filter(status__iexact=txn_status)
            
        return queryset

class WithdrawalRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WithdrawalRequestSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            with db_transaction.atomic():
                new_request = Transaction.objects.create(
                    user=request.user,
                    amount=serializer.validated_data['amount'],
                    transaction_type='withdrawal',
                    status='pending',
                    reference=f"WD-{request.user.id}-{Transaction.objects.count() + 1}"
                )
            return Response(TransactionSerializer(new_request).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class PayoutAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PayoutAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, created = PayoutAccount.objects.get_or_create(user=self.request.user)
        return obj

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)



class VerifyTicketView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
   
        ticket_code = request.data.get('ticket_code')
        
        if not ticket_code:
            return Response(
                {"detail": "Invalide ticket  provided."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        ticket = get_object_or_404(
            Ticket, 
            ticket_code=ticket_code, 
            event__user=request.user
        )

        if not ticket.is_perchased:
            return Response(
                {"detail": "This ticket has not been sold yet."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if ticket.is_verified or getattr(ticket, 'is_used', False):
            return Response(
                {
                    "status": "denied",
                    "detail": "Access Denied: This ticket has already been used.",
                    "customer_name": getattr(ticket, 'customer_name', "Guest")
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

        ticket.is_verified = True
        if hasattr(ticket, 'is_used'):
            ticket.is_used = True
        
        ticket.save()

        return Response({
            "status": "success",
            "message": "Verification Successful: Access Granted",
            "data": {
                "ticket_code": ticket.ticket_code,
                "category": ticket.category.name,
                "customer_name": getattr(ticket, 'customer_name', 'Verified Guest'),
            }
        }, status=status.HTTP_200_OK)
    


class TicketPurchaseView(generics.GenericAPIView):
    serializer_class = TicketPurchaseSerializer

    def post(self, request, ticket_id):
        ticket = get_object_or_404(Ticket, id=ticket_id)
        
        serializer = self.get_serializer(data=request.data, context={'ticket': ticket})

        if serializer.is_valid():
            try:
                with db_transaction.atomic():
                    txn = serializer.save()
                    gateway = PaymentGateWay()

                    payment_response = gateway.receive_money(txn)

                if payment_response:
                    return Response(
                        {
                            "status": "success",
                            "message": "Payment prompt sent! Please check your phone and enter your MoMo PIN to complete the purchase.",
                            "data": {
                                "transaction_id": txn.reference, 
                                "internal_id": txn.id,
                                "ticket_code": str(ticket.ticket_code),
                                "price": str(ticket.price)
                                
                            }
                        },
                        status=status.HTTP_201_CREATED
                    )
                else:
                    txn.status = "failed"
                    txn.save()
                    return Response(
                        {"error": "Failed to initiate payment. Please check your number and try again."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            except Exception as e:
                return Response(
                    {"error": f"An error occurred: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TransactionVerifyView(APIView):
    
    def get(self, request, reference):
        txn = get_object_or_404(Transaction, reference=reference)

        if txn.status == "success":
            return Response({
                "status": "success", 
                "message": "Payment already processed."
            })

        gateway = PaymentGateWay()
        verification_data = gateway.verify_transaction(reference)

        if not verification_data:
            return Response(
                {"error": "Could not connect to payment provider."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        gw_status = verification_data.get("status")
        gw_amount = Decimal(str(verification_data.get("amount", 0)))
        gw_amount_paid = Decimal(str(verification_data.get("amount_paid", 0)))
       
        txn_amount = (txn.amount + getattr(txn, 'bx_charge', Decimal('0.00')))
        if gw_status == "success":

            if gw_amount == txn_amount:
                try:
                    with db_transaction.atomic():

                        txn.amount_paid = gw_amount_paid + getattr(txn, 'bx_charge', Decimal('0.00'))
                        txn.status = "success"
                        txn.save()

                        if txn.ticket:
                            ticket = txn.ticket
                            ticket.is_perchased = True 
                            ticket.save()

                            event = ticket.event
                            event.balance += txn.amount
                            event.save()

                    return Response({
                        "status": "success",
                        "message": "Payment is completed successfully.",
                        "data": {
                            "reference": txn.reference,
                            "ticket_code": ticket.ticket_code,
                            "phone_nunber":txn.phone_number,
                            "pin":txn.pin_code
                        }
                    }, status=status.HTTP_200_OK)

                except Exception as e:
                    return Response(
                        {"error": f"Database update failed: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
           
                return Response(
                    {"error": "Amount mismatch. Verification failed for security reasons."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        elif gw_status == "failed":
            txn.status = "failed"
            txn.save()
            return Response({"status": "failed", "message": "Payment failed at gateway."})

        return Response({
            "status": "pending",
            "message": "Waiting for mom's PIN to complete the purchase."
        })


class RetrieveTicketView(APIView):
    def get(self, request):
        pin = request.query_params.get('pin')
        phone_number = request.query_params.get('phone_number')

        if not pin or not phone_number:
            return Response({"error": "PIN and Phone Number required."}, status=400)

        transactions = Transaction.objects.filter(
            pin_code=pin, 
            phone_number=phone_number
        ).select_related('ticket', 'ticket__event')

        if not transactions.exists():
            return Response({"error": "No tickets found."}, status=404)

        response_data = [
            {
                "ticket": TicketSerializer(tx.ticket).data,
                "event": EventTicketSerializer(tx.ticket.event).data if tx.ticket and hasattr(tx.ticket, 'event') else None
            }
            for tx in transactions if tx.ticket
        ]

        return Response(response_data, status=200)

        

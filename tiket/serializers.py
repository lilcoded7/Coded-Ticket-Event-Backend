from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import User
from .models import *


class LoginUserSerializer(serializers.Serializer):
    class Meta:
        model = User
        fields = ["username", "password"]

    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    user_id = serializers.UUIDField(read_only=True)
    access_token = serializers.CharField(read_only=True)
    refresh_token = serializers.CharField(read_only=True)

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"), username=username, password=password
        )

        if not user:
            raise AuthenticationFailed("Invalid username or password")

        if not user.is_active:
            raise AuthenticationFailed("User account is disabled")

        refresh = RefreshToken.for_user(user)

        return {
            "username": user.username,
            "user_id": str(user.id),
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        }


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"


class OrganizerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields=['username']

class EventTicketSerializer(serializers.ModelSerializer):
    user = OrganizerSerializer()
    class Meta:
        model = Event
        fields = ['user', 'balance']


class BulkTicketCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1, write_only=True)

    def create(self, validated_data):
        quantity = validated_data.pop("quantity")
        category = validated_data["category"]
        name = validated_data.get("name") or category.name

        event = Event.objects.first()

        tickets = []
        for _ in range(quantity):
            ticket = Ticket(
                event=event,
                name=name,
                category=category,
                price=validated_data["price"],
                quantity_available=1,
            )
            tickets.append(ticket)

        for t in tickets:
            t.save()

        return tickets


class BenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Benefit
        fields = ["id", "name"]


class CategorySerializer(serializers.ModelSerializer):
    benefits = BenefitSerializer(source="benefit_set", many=True, read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "image", "benefits"]


class TicketListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "name",
            "category",
            "price",
            "is_used",
        ]

class TicketSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = '__all__'


class TicketPurchaseSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=True)
    pin_code = serializers.CharField(required=True, min_length=4, max_length=6)

    class Meta:
        model = Transaction
        fields = ["phone_number", "pin_code"]

    def validate(self, data):
        ticket = self.context.get("ticket")
        if ticket.is_perchased:
            raise serializers.ValidationError("This ticket has already been sold.")
        return data

    def create(self, validated_data):
        ticket = self.context.get("ticket")

        transaction = Transaction.objects.create(
            ticket=ticket,
            amount=ticket.price,
            transaction_type="collection",
            status="pending",
            **validated_data,
        )
        ticket.save()

        return transaction


# dashboard below


class DashboardEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["name", "location", "flyer", "logo", "description"]


class TicketCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["name", "image"]


class DashboardTicketSerializer(serializers.ModelSerializer):
    category = TicketCategorySerializer(read_only=True)
    event = EventSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = ["id", "event", "category", "price", "is_perchased", "created_at"]


class CreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


# Transaction below


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["phone_number", "amount", "transaction_type", "status"]


class WithdrawalRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1000)

    def validate(self, data):
        user = self.context["request"].user

        if not PayoutAccount.objects.filter(user=user).exists():
            raise serializers.ValidationError("No linked payout account found.")

        total_revenue = (
            Transaction.objects.filter(
                user=user, transaction_type="collection", status="successful"
            ).aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

        total_withdrawn = (
            Transaction.objects.filter(user=user, transaction_type="withdrawal")
            .exclude(status="failed")
            .aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

        balance = Event.objects.first().balance or 0

        if data["amount"] > balance:
            raise serializers.ValidationError(
                f"Insufficient funds. Available: {balance}"
            )

        return data


class PayoutAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutAccount
        fields = [
            "account_type",
            "bank_name",
            "account_number",
            "momo_number",
            "momo_name",
        ]

    def validate(self, data):
        if data.get("account_type") == "bank":
            if not data.get("bank_name") or not data.get("account_number"):
                raise serializers.ValidationError(
                    "Bank name and account number are required for bank payouts."
                )
        elif data.get("account_type") == "momo":
            if not data.get("momo_number") or not data.get("momo_name"):
                raise serializers.ValidationError(
                    "Momo number and subscriber name are required for momo payouts."
                )
        return data

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
import qrcode
from io import BytesIO
from django.db import models
import uuid


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class CodedProperty(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user.username} - {self.balance}"


class Event(models.Model):
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    logo = models.ImageField(upload_to="event_logos/", null=True, blank=True)
    flyer = models.ImageField(upload_to="event_flyers/", null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.pk and Event.objects.exists():
            raise ValidationError("There can be only one Event instance.")
        return super(Event, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Event (Single Instance)"


class Category(BaseModel):
    name = models.CharField(max_length=255)
    image = models.ImageField(null=True, blank=True)

    def __str__(self):
        return self.name


class Ticket(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_available = models.PositiveIntegerField()
    ticket_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_used = models.BooleanField(default=False)
    is_perchased = models.BooleanField(default=False)
    purchased_at = models.DateTimeField(auto_now_add=True)
    qr_code = models.ImageField(upload_to="qr_codes/", blank=True, null=True)

    is_verified = models.BooleanField(default=False)
    ticket_image = models.ImageField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Only generate QR if it doesn't exist
        if not self.qr_code:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(str(self.ticket_code))
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")

            file_name = f"qr_{self.ticket_code}.png"
            self.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ticket {self.ticket_code}"


class Transaction(BaseModel):
    TRANSACTION_TYPES = (
        ("collection", "collection"),
        ("withdrawal", "withdrawal"),
    )
    STATUS = (
        ("pending", "pending"),
        ("success", "success"),
        ("failed", "failed"),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    reference = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS, default="pending", null=True, blank=True
    )
    pin_code = models.CharField(max_length=6, null=True, blank=True)
    
    bx_charge = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    gross_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    amount_paid=models.DecimalField(max_digits=20, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount}"


class Benefit(BaseModel):
    name = models.CharField(max_length=255)
    category = models.ManyToManyField(Category)

    def __str__(self):
        return self.name



class PayoutAccount(models.Model):
    ACCOUNT_TYPES = (
        ('bank', 'Bank Account'),
        ('momo', 'Mobile Money'),
    )

    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='payout_account'
    )
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    
    # Bank Specific Fields
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Momo Specific Fields
    momo_number = models.CharField(max_length=20, blank=True, null=True)
    momo_name = models.CharField(max_length=255, blank=True, null=True)
    
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_account_type_display()}"
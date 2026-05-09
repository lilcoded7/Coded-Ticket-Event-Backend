from decimal import Decimal
from django.conf import settings
import random
import string
import requests


class PaymentGateWay:
    def __init__(self):
        self.baseurl = "https://mp1.hstonline.tech"
        self.token = settings.HSTPAY_TOKEN
        self.merchant_id = settings.HSTPAY_MERCHANT_ID
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json",
        }

    def get_network(self, phone_number: str) -> str:
        """Determines the network provider based on the phone number prefix."""
        if phone_number.startswith("233"):
            phone_number = f"0{phone_number[3:]}"
        elif phone_number.startswith("+233"):
            phone_number = f"0{phone_number[4:]}"
            
        prefix = phone_number[:3]
        
        networks = {
            "MTN": ["024", "054", "055", "059", "025", "053"],
            "VDF": ["020", "050"],
            "ATL": ["027", "057", "026", "056"]
        }
        
        for net, prefixes in networks.items():
            if prefix in prefixes:
                return net
        return "UNKNOWN"

    def receive_money(self, tx) -> dict | bool:
        """Triggers a MoMo collection prompt using the transaction reference."""
        phone_number = tx.phone_number
        
        if phone_number.startswith("233"):
            phone_number = f"0{phone_number[3:]}"
        elif phone_number.startswith("+233"):
            phone_number = f"0{phone_number[4:]}"

        network = self.get_network(phone_number)
        
        if not tx.reference:
            import uuid
            tx.reference = str(uuid.uuid4())[:12] 
        
        charge = Decimal('2.00')
        
        current_amount =(tx.amount+charge)

        try:
            url = f"{self.baseurl}/api/merchants/tela/{self.merchant_id}/"
            
            data = {
                "amount": float(current_amount) if isinstance(tx.amount, Decimal) else tx.amount,
                "phoneNumber": phone_number,
                "network": network,
                "reference": tx.reference, 
            }

            response = requests.post(url, json=data, headers=self.headers)

            if response.status_code in [200, 201]:
                response_data = response.json()
                tx.reference = response_data.get("transaction_id")
                tx.bx_charge = charge
                tx.net_amount = tx.amount
                tx.gross_amount = tx.amount+charge
                tx.save()
                return response_data
            
            print(f"Gateway Error: {response.status_code} - {response.text}")
            return False

        except requests.exceptions.RequestException as e:
            print(f"Connection Error: {str(e)}")
            return False

    def verify_transaction(self, reference: str):
        """Verifies the status of a transaction using the reference."""
        url = f"{self.baseurl}/api/transactions/verify/{reference}"
        try:
            response = requests.get(url, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except requests.exceptions.RequestException:
            return None

    def get_merchant_balance(self) -> float:
        """Fetches the current wallet balance for the merchant."""
        url = f"{self.baseurl}/api/merchants/getMerchant"
        try:
            res = requests.get(url, headers=self.headers)
            if res.status_code == 200:
                return res.json().get("current_balance", 0.00)
        except Exception:
            pass
        return 0.00
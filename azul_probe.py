import asyncio, json, sys
from pyazul.core.config import AzulSettings
from pyazul.api.client import AzulAPI

auth = sys.argv[1]
cert = open("/tmp/azul_cert.pem").read()
key = open("/tmp/azul_key.pem").read()
import os
os.environ["AZUL_CERT"] = cert
os.environ["AZUL_KEY"] = key
settings = AzulSettings(
    AUTH1=auth, AUTH2=auth,
    MERCHANT_ID="39038540035",
    ENVIRONMENT="dev",
    AZUL_CERT=cert, AZUL_KEY=key,
    CHANNEL="EC",
)
api = AzulAPI(settings=settings)
data = {
    "Channel": "EC", "Store": "39038540035", "PosInputMode": "E-Commerce",
    "Amount": "4000", "Itbis": "000", "OrderNumber": "PROBE001",
    "CustomOrderId": "PROBE001", "TrxType": "Sale", "AcquirerRefData": "1",
    "CardNumber": "4005520000000129", "Expiration": "202812", "CVC": "123",
    "ForceNo3DS": "0",
    "CardHolderInfo": {"Name": "Test Probe", "Email": "probe@test.com"},
    "ThreeDSAuth": {
        "TermUrl": "http://localhost:8092/payment/azul/3ds_return",
        "MethodNotificationUrl": "http://localhost:8092/payment/azul/3ds_return",
        "RequestChallengeIndicator": "03",
    },
}
try:
    r = asyncio.run(api._async_request(data, is_secure=True))
    print(json.dumps({k: (str(v)[:120]) for k, v in r.items()}, indent=1))
except Exception as e:
    print("PROBE ERROR:", type(e).__name__, str(e)[:400])

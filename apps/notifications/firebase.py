import os
import json
import base64
import logging
import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger(__name__)


def init_firebase():
    if firebase_admin._apps:
        return

    b64 = os.getenv("FIREBASE_CREDENTIALS_B64")

    if not b64:
        raise ValueError("FIREBASE_CREDENTIALS_B64 is not configured")

    try:
        decoded = base64.b64decode(b64)
        service_account_info = json.loads(decoded)

        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")

    except Exception as e:
        logger.exception("Firebase initialization failed: %s", e)
        raise
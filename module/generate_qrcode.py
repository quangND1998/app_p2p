from config_env import VIETQR_KEY, VIETQR_SECRET,ACQID, ACCOUNTNAME, ACQID,ACCOUNTNO
import requests
import base64
import io
import logging
import json
from rapidfuzz import process
import unicodedata
import re
import os


bank_dict_path =  os.path.join(os.path.dirname(os.path.dirname(__file__)), "bank_list.json")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def generate_vietqr(accountno=ACCOUNTNO, accountname=ACCOUNTNAME, acqid=ACQID, addInfo='', amount='', template=''):
    url = "https://api.vietqr.io/v2/generate"
    headers = {
        "x-client-id": VIETQR_KEY,
        "x-api-key": VIETQR_SECRET,
        "Content-Type": "application/json"
    }
    payload = {
        "accountNo": accountno,
        "accountName": accountname,
        "acqId": acqid,
        "addInfo": addInfo, # Additional information for the transaction
        "amount": amount, # Amount in VND
        "template": template # Template for the QR code
    }

    response = requests.post(url, json=payload, headers=headers)
    qr_data_url = response.json()["data"]["qrDataURL"]
    header, encoded = qr_data_url.split(",", 1)
    image_data = base64.b64decode(encoded)
    return io.BytesIO(image_data)

def get_nganhang_api():
    url = 'https://api.vietqr.io/v2/banks'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        banks = response.json()
        logger.info("Fetched bank list successfully.")
        return banks
    except requests.RequestException as e:
        logger.error(f"Failed to fetch bank list: {e}")
        return None

def get_nganhang_id(name_bank: str) -> str:
    try:
        with open(bank_dict_path, 'r', encoding="utf-8") as f:
            banks = json.load(f)
            list_banks = list(banks.keys())
            result = find_best_match(name_bank, list_banks)
            if result:
                key, score = result
                if score >= 88:
                    logger.info(f"Best match: {key} with accuracy: {score}")
                    return banks[key].get("bin")
                else:
                    logger.warning(f"Low confidence match for '{name_bank}': {key} ({score})")
            else:
                logger.warning(f"No match found for {name_bank}")
            return None
    except FileNotFoundError:
        logger.error("bank_list.json not found.")
        return None
    except json.JSONDecodeError:
        logger.error("Invalid JSON format in bank_list.json.")
        return None
    except Exception as e:  
        logger.error(f"Unexpected error: {e}")
        return None

def normalize_text(text):
    try:
        text = text.lower()
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        text = re.sub(r'[^a-z0-9\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        logger.error(f"Error normalizing text: {e}")
        return text

def find_best_match(query, choices):
    try:
        norm_query = normalize_text(query)
        norm_choices = [normalize_text(c) for c in choices]
        match = process.extractOne(norm_query, norm_choices)
        if match:
            original_match = choices[norm_choices.index(match[0])]
            return original_match, match[1]
        return None
    except Exception as e:
        logger.error(f"Error finding best match: {e}")
        return None
    
if __name__ == '__main__':
    print(get_nganhang_id("Vietinbank ( Chau Duc Lam )"))

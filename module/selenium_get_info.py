from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import os
import time
import re
import subprocess
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config_env import CHROME_DRIVE, CHROME_PATH


profile_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Default")

def extract_info_by_key(data):
    result = {}
    for key, value in data.items():
        key_lower = key.lower()

        if re.search(r'fiat amount', key_lower):
            result['Fiat amount'] = value

        elif re.search(r'reference message', key_lower):
            result['Reference message'] = value

        elif re.search(r'^name$|full name', key_lower):
            result['Full Name'] = value

        elif re.search(r'bank card|account number', key_lower):
            result['Bank Card'] = value

        elif re.search(r'bank name', key_lower):
            result['Bank Name'] = value
            
    return result

def create_options(headless: bool = False,port=9222):
    chrome_options = Options()
    # chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument(f'user-data-dir={profile_path}')
    # chrome_options.add_argument('--disable-extensions')
    # chrome_options.add_argument("--disable-dev-shm-usage")
    # chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # chrome_options.add_experimental_option('useAutomationExtension', False)
    # chrome_options.add_argument('--no-sandbox')
    chrome_options.debugger_address = f"127.0.0.1:{port}"
    if headless:
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
    else:
        chrome_options.add_argument('--window-size=600,400')
    return chrome_options

def create_driver(headless: bool = True):
    return webdriver.Chrome(
            options=create_options(headless=headless),
            #service=Service(f'{CHROME_DRIVE}')
            service=Service(ChromeDriverManager().install())
)
 
def extract_order_info(order_no: str) -> dict:
    def parse_currency(vnd_str):
        try:
            return float(vnd_str.replace("₫", "").replace(",", "").strip())
        except Exception as e:
            print(f"[LỖI] parse_currency: {e}")
            return None

    driver = None
    bank_info = {}
    label,value = None, None
    try:
        driver = create_driver(False)
        driver.execute_script("window.open('');")
        tabs = driver.window_handles
        driver.switch_to.window(tabs[-1])
        
        driver.get(f"https://p2p.binance.com/en/fiatOrderDetail?orderNo={order_no}")
        time.sleep(3)
        WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.subtitle6.text-textBuy'))  # sửa lại selector theo thực tế
                )
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        fiat_block = soup.select_one("div.subtitle6.text-textBuy")
        if fiat_block:
            fiat_amount = fiat_block.get_text(strip=True)
            bank_info["Fiat amount"] =  parse_currency(fiat_amount)

        sections = soup.find('div',class_='relative w-full')
        label_tag,value_tag = None, None
        for section in sections:
            all_divs = section.find_all("div")  
            for div in all_divs:
                if div.get("class") and "body2" in div.get("class") and "text-tertiaryText" in div.get("class"):
                    label_tag = div
                if div.get("class") and "body2" in div.get("class") and "text-right" in div.get("class") and "break-words" in div.get("class"):
                    value_tag = div

                if label_tag and value_tag:
                    label = label_tag.text.strip()
                    value = value_tag.text.strip()
                    bank_info[label] = value
                    label,value = None, None

        print(f"[THÀNH CÔNG] Đã trích xuất thông tin: {bank_info}")
        driver.close()    
    except Exception as e:
        print(f"[LỖI] Lỗi khi trích xuất dữ liệu: {e}")

    finally:
        if driver:
            driver.quit()
    return bank_info

def launch_chrome_remote_debugging(port=9222):
    chrome_path = f"{CHROME_PATH}"
    user_data_dir = f"{profile_path}"
    # Kiểm tra Chrome tồn tại
    if not os.path.exists(chrome_path):
        raise FileNotFoundError(f"Không tìm thấy Chrome tại: {chrome_path}")
    command = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f'--user-data-dir={user_data_dir}',
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window"
    ]
    subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)
    
def login_app():
    driver = None
    bank_info = {}
    try:
        driver = create_driver(False)
        driver.execute_script("window.open('');")
        tabs = driver.window_handles
        driver.switch_to.window(tabs[-1])
        driver.get(f"https://p2p.binance.com/en")
        driver.implicitly_wait(60)
        print(f"[THÀNH CÔNG]")

    except Exception as e:
        print(f"[LỖI]: {e}")
    finally:
        if driver:
            driver.quit()
    return bank_info

if __name__ == "__main__":
    login_app()

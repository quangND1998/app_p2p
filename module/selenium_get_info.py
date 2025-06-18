"""
Module này được sử dụng để tự động hóa trình duyệt Chrome cho ứng dụng Binance P2P Trading.
Mục đích: Tự động hóa các thao tác đăng nhập và lấy thông tin giao dịch từ Binance P2P.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import os
import time
import re
import subprocess
import sys
import logging
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config_env import CHROME_DRIVE, CHROME_PATH
from webdriver_manager.chrome import ChromeDriverManager

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sử dụng Path để xử lý đường dẫn an toàn hơn
BASE_DIR = Path(__file__).parent.parent
PROFILE_PATH = BASE_DIR / "Default"

def extract_info_by_key(data):
    """Trích xuất thông tin từ dữ liệu giao dịch"""
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        # Map các trường dữ liệu
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

def create_options(headless: bool = False, port: int = 9222) -> Options:
    """Tạo Chrome options với các cài đặt an toàn"""
    chrome_options = Options()
    
    # Các tùy chọn cơ bản và bảo mật
    chrome_options.add_argument(f'user-data-dir={str(PROFILE_PATH)}')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-infobars')
    
    # Cài đặt headless nếu cần
    if headless:
        chrome_options.add_argument('--headless=new')
    else:
        chrome_options.add_argument('--window-size=600,400')
    
    return chrome_options

def create_driver(headless: bool = True) -> webdriver.Chrome:
    """Tạo Chrome driver với các cài đặt an toàn"""
    try:
        return webdriver.Chrome(
            options=create_options(headless=headless),
            service=Service(ChromeDriverManager().install())
        )
    except Exception as e:
        logger.error(f"Lỗi khi tạo driver: {e}")
        raise

def extract_order_info(order_no: str) -> dict:
    def parse_currency(vnd_str):
        try:
            return float(vnd_str.replace("₫", "").replace(",", "").strip())
        except Exception as e:
            logger.error(f"[LỖI] parse_currency: {e}")
            return None

    driver = None
    bank_info = {}
    label,value = None, None
    try:
        logger.info(f"🚀 Bắt đầu trích xuất thông tin cho order: {order_no}")
        driver = create_driver(False)
        driver.execute_script("window.open('');")
        tabs = driver.window_handles
        driver.switch_to.window(tabs[-1])
        
        url = f"https://p2p.binance.com/en/fiatOrderDetail?orderNo={order_no}"
        logger.info(f"🌐 Đang truy cập URL: {url}")
        driver.get(url)
        time.sleep(3)
        
        logger.info("⏳ Đang chờ trang load...")
        WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.subtitle6.text-textBuy'))
                )
        logger.info("✅ Trang đã load thành công")
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        logger.info("📄 Đã parse HTML thành công")
        
        # Tìm fiat amount
        fiat_block = soup.select_one("div.subtitle6.text-textBuy")
        if fiat_block:
            fiat_amount = fiat_block.get_text(strip=True)
            bank_info["Fiat amount"] = parse_currency(fiat_amount)
            logger.info(f"💰 Tìm thấy Fiat Amount: {fiat_amount} -> {bank_info['Fiat amount']}")
        else:
            logger.warning("⚠️ Không tìm thấy Fiat Amount block")

        # Tìm các thông tin khác
        sections = soup.find('div',class_='relative w-full')
        if not sections:
            logger.warning("⚠️ Không tìm thấy section chính")
            return bank_info
            
        label_tag,value_tag = None, None
        found_fields = 0
        
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
                    found_fields += 1
                    logger.info(f"📋 Tìm thấy field: {label} = {value}")
                    label,value = None, None

        logger.info(f"📊 Tổng số fields tìm thấy: {found_fields}")
        logger.info(f"🎯 Thông tin cuối cùng: {bank_info}")
        
        driver.close()
        logger.info("✅ Hoàn thành trích xuất thông tin")
        
    except Exception as e:
        logger.error(f"💥 Lỗi khi trích xuất dữ liệu cho order {order_no}: {str(e)}", exc_info=True)

    finally:
        if driver:
            driver.quit()
            logger.info("🔒 Đã đóng driver")
    return bank_info

def launch_chrome_remote_debugging(port: int = 9222) -> None:
    """Khởi chạy Chrome với chế độ remote debugging"""
    chrome_path = Path(CHROME_PATH)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Không tìm thấy Chrome tại: {chrome_path}")
    
    # Tạo command với các tham số an toàn
    command = [
        str(chrome_path),
        f"--remote-debugging-port={port}",
        f'--user-data-dir={str(PROFILE_PATH)}',
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        "--disable-extensions",
        "--disable-popup-blocking",
        "--disable-notifications"
    ]
    
    try:
        # Sử dụng subprocess.Popen với các tham số an toàn
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW  # Ẩn console window
        )
        time.sleep(3)  # Đợi Chrome khởi động
        logger.info("Chrome đã được khởi chạy thành công")
    except Exception as e:
        logger.error(f"Lỗi khi khởi chạy Chrome: {e}")
        raise

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

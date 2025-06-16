import os
import json
from datetime import datetime
from io import BytesIO
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class TransactionStorage:
    def __init__(self, base_dir: str = "transactions"):
        """Khởi tạo TransactionStorage với thư mục cơ sở"""
        self.base_dir = Path(base_dir)
        self.qr_dir = self.base_dir / "qr_codes"
        self.logger = logging.getLogger(__name__)
        
        # Tạo thư mục nếu chưa tồn tại
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.qr_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_date_file_path(self, date: datetime) -> Path:
        """Lấy đường dẫn file JSON cho một ngày cụ thể"""
        date_str = date.strftime("%Y-%m-%d")
        return self.base_dir / f"transactions_{date_str}.json"
        
    def _get_qr_filename(self, transaction_type: str, order_number: str, timestamp: datetime) -> str:
        """Tạo tên file cho mã QR"""
        date_str = timestamp.strftime("%Y%m%d_%H%M%S")
        return f"{transaction_type}_{date_str}_{order_number}.png"
        
    def save_transaction(self, transaction_info: dict, qr_image: bytes = None) -> dict:
        """Lưu thông tin giao dịch và mã QR"""
        try:
            # Lấy timestamp từ transaction_info hoặc sử dụng thời gian hiện tại
            timestamp = datetime.fromtimestamp(transaction_info.get('timestamp', datetime.now().timestamp()))
            date_file = self._get_date_file_path(timestamp)
            
            # Đọc dữ liệu hiện có hoặc tạo mới
            transactions = []
            if date_file.exists():
                with open(date_file, 'r', encoding='utf-8') as f:
                    transactions = json.load(f)
            
            # Thêm thông tin giao dịch mới
            transaction_info['timestamp'] = timestamp.timestamp()
            
            # Lưu mã QR nếu có
            if qr_image:
                qr_filename = self._get_qr_filename(
                    transaction_info['type'],
                    transaction_info['order_number'],
                    timestamp
                )
                qr_path = self.qr_dir / qr_filename
                with open(qr_path, 'wb') as f:
                    f.write(qr_image)
                transaction_info['qr_path'] = str(qr_path)
            
            # Thêm vào danh sách và lưu lại
            transactions.append(transaction_info)
            with open(date_file, 'w', encoding='utf-8') as f:
                json.dump(transactions, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Đã lưu giao dịch {transaction_info['order_number']} vào file {date_file}")
            return transaction_info
            
        except Exception as e:
            self.logger.error(f"Lỗi khi lưu giao dịch: {e}")
            raise
            
    def get_transactions_by_date(self, date: datetime) -> list:
        """Lấy danh sách giao dịch theo ngày"""
        try:
            date_file = self._get_date_file_path(date)
            if not date_file.exists():
                return []
                
            with open(date_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            self.logger.error(f"Lỗi khi đọc giao dịch ngày {date}: {e}")
            return []
            
    def get_transactions_by_date_range(self, start_date: datetime, end_date: datetime) -> list:
        """Lấy danh sách giao dịch trong khoảng thời gian"""
        try:
            all_transactions = []
            current_date = start_date
            
            while current_date <= end_date:
                transactions = self.get_transactions_by_date(current_date)
                all_transactions.extend(transactions)
                current_date = current_date.replace(day=current_date.day + 1)
                
            return all_transactions
            
        except Exception as e:
            self.logger.error(f"Lỗi khi đọc giao dịch từ {start_date} đến {end_date}: {e}")
            return []
            
    def get_transaction_by_order(self, order_number: str) -> dict:
        """Tìm giao dịch theo số order"""
        try:
            # Tìm trong tất cả các file JSON
            for date_file in self.base_dir.glob("transactions_*.json"):
                with open(date_file, 'r', encoding='utf-8') as f:
                    transactions = json.load(f)
                    for transaction in transactions:
                        if transaction.get('order_number') == order_number:
                            return transaction
            return None
            
        except Exception as e:
            self.logger.error(f"Lỗi khi tìm giao dịch {order_number}: {e}")
            return None
            
    def get_recent_transactions(self, limit: int = 10) -> list:
        """Lấy danh sách giao dịch gần đây nhất"""
        try:
            all_transactions = []
            
            # Đọc tất cả các file JSON
            for date_file in sorted(self.base_dir.glob("transactions_*.json"), reverse=True):
                with open(date_file, 'r', encoding='utf-8') as f:
                    transactions = json.load(f)
                    all_transactions.extend(transactions)
                    
            # Sắp xếp theo thời gian và lấy limit giao dịch gần nhất
            all_transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return all_transactions[:limit]
            
        except Exception as e:
            self.logger.error(f"Lỗi khi lấy giao dịch gần đây: {e}")
            return [] 
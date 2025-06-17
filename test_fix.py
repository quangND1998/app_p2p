#!/usr/bin/env python3
"""
Script test đơn giản để kiểm tra việc sửa lỗi BytesIO
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from module.generate_qrcode import generate_vietqr
from module.transaction_storage import TransactionStorage
from datetime import datetime

def test_bytesio_fix():
    """Test việc sửa lỗi BytesIO"""
    print("🧪 Bắt đầu test sửa lỗi BytesIO...")
    
    try:
        # Test tạo QR code
        print("1️⃣ Tạo QR code...")
        qr_image = generate_vietqr(
            accountno="1234567890",
            accountname="Test User",
            acqid="970436",
            addInfo="Test reference",
            amount=1000000,
            template="rc9Vk60"
        )
        print(f"✅ QR code được tạo: {type(qr_image)}")
        
        # Test chuyển đổi BytesIO thành bytes
        print("2️⃣ Chuyển đổi BytesIO thành bytes...")
        qr_bytes = qr_image.getvalue()
        print(f"✅ Bytes được tạo: {type(qr_bytes)}, kích thước: {len(qr_bytes)} bytes")
        
        # Test lưu vào storage
        print("3️⃣ Test lưu vào storage...")
        storage = TransactionStorage("test_fix_transactions")
        
        transaction_info = {
            "type": "buy",
            "order_number": "TEST_FIX_123",
            "amount": 1000000,
            "bank_name": "Vietcombank",
            "account_number": "1234567890",
            "account_name": "Test User",
            "reference": "Test reference",
            "message": "Test transaction for BytesIO fix",
            "timestamp": datetime.now().timestamp()
        }
        
        saved_transaction = storage.save_transaction(transaction_info, qr_bytes)
        print(f"✅ Transaction được lưu: {saved_transaction['order_number']}")
        print(f"📁 QR path: {saved_transaction.get('qr_path', 'N/A')}")
        
        # Kiểm tra file QR có tồn tại không
        if 'qr_path' in saved_transaction:
            import os
            if os.path.exists(saved_transaction['qr_path']):
                file_size = os.path.getsize(saved_transaction['qr_path'])
                print(f"✅ File QR tồn tại, kích thước: {file_size} bytes")
            else:
                print("❌ File QR không tồn tại")
        
        print("🎉 Test hoàn thành thành công!")
        return True
        
    except Exception as e:
        print(f"💥 Lỗi trong quá trình test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_bytesio_fix()
    if success:
        print("\n✅ Lỗi BytesIO đã được sửa thành công!")
    else:
        print("\n❌ Vẫn còn lỗi BytesIO!") 
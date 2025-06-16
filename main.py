from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QPushButton, 
                           QLabel, QVBoxLayout, QPlainTextEdit, QFileDialog, 
                           QDateEdit, QMessageBox, QHBoxLayout, QTabWidget, 
                           QGroupBox, QLineEdit, QTextEdit, QComboBox, 
                           QSpinBox, QDoubleSpinBox, QTableWidget, QHeaderView, 
                           QTableWidgetItem)
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QDate, QThread, Qt
from PyQt5.QtGui import QFont, QIcon, QPixmap, QImage

import sys
import logging
from module.selenium_get_info import login_app, launch_chrome_remote_debugging
from module.binance_p2p import P2PBinance
from datetime import datetime
import tracemalloc
import os
import time
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from module.generate_qrcode import generate_vietqr, get_bank_bin
from dotenv import load_dotenv
from module.transaction_storage import TransactionStorage
from transaction_viewer import TransactionViewer

# Load biến môi trường
load_dotenv()
BINANCE_KEY = os.getenv("BINANCE_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET")

tracemalloc.start()

class LogHandler(logging.Handler, QObject):
    log_signal = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg)
        
class ChromeThread(QThread):
    def run(self):
        launch_chrome_remote_debugging()

class Worker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, func):
        super().__init__()
        self.func = func

    def run(self):
        try:
            self.func()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.p2p_instance = P2PBinance()
        self.transaction_storage = TransactionStorage()
        self.chrome_thread = ChromeThread()
        self.initUI()
        self.init_logging()
        
    def initUI(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle('Binance P2P Trading')
        self.setGeometry(100, 100, 1200, 800)
        
        # Widget chính
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)  # Kết nối signal tab changed
        layout.addWidget(self.tab_widget)
        
        # Tab chính (giữ nguyên giao diện cũ)
        main_tab = QWidget()
        main_layout = QVBoxLayout(main_tab)
        
        # Phần Chrome và đăng nhập
        self.label_open = QLabel("Google Chrome")
        self.open_button = QPushButton("Open Chrome")
        self.open_button.clicked.connect(self.chrome_thread.start)

        self.label_login = QLabel("Đăng nhập Binance")
        self.login_button = QPushButton("Đăng nhập")
        self.login_button.clicked.connect(self.handle_login)

        self.label_run_app = QLabel("Chạy chương trình")
        self.run_button = QPushButton("RUN")
        self.run_button.clicked.connect(self.handle_run_app)

        self.stop_button = QPushButton("DỪNG")
        self.stop_button.clicked.connect(self.handle_stop)
        self.stop_button.setEnabled(False)

        self.clear_log_button = QPushButton("Xóa Log")
        self.clear_log_button.clicked.connect(self.clear_log)

        # Thêm các widget vào layout chính
        for widget in [
            self.label_open, self.open_button,
            self.label_login, self.login_button,
            self.label_run_app, self.run_button, self.stop_button,
            self.clear_log_button
        ]:
            main_layout.addWidget(widget)

        # Phần QR code (giữ nguyên)
        self.generate_qr_button = QPushButton("Tạo QR")
        self.generate_qr_button.clicked.connect(self.generate_qr)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setMinimumSize(300, 300)
        self.qr_label.setStyleSheet("QLabel { background-color: white; border: 1px solid #ccc; }")
        self.qr_label.hide()

        self.save_qr_button = QPushButton("Lưu mã QR")
        self.save_qr_button.clicked.connect(self.save_qr_image)
        self.save_qr_button.setEnabled(False)
        self.save_qr_button.hide()

        qr_layout = QVBoxLayout()
        qr_layout.addWidget(QLabel("Mã QR VietQR:"))
        qr_layout.addWidget(self.qr_label)
        qr_layout.addWidget(self.save_qr_button)
        qr_layout.addWidget(self.generate_qr_button)
        main_layout.addLayout(qr_layout)

        # Phần log
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(1000)
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # Tab giao dịch mới
        trade_tab = QWidget()
        trade_layout = QVBoxLayout(trade_tab)
        
        # Phần tìm kiếm
        search_group = QGroupBox("Tìm kiếm giao dịch")
        search_layout = QVBoxLayout()
        
        # Phần chọn ngày
        date_layout = QHBoxLayout()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self.search_transactions)
        date_layout.addWidget(QLabel('Ngày:'))
        date_layout.addWidget(self.date_edit)
        
        # Thêm nút clear search
        self.clear_search_btn = QPushButton('Xóa tìm kiếm')
        self.clear_search_btn.clicked.connect(self.clear_search)
        date_layout.addWidget(self.clear_search_btn)
        
        search_layout.addLayout(date_layout)
        
        # Phần tìm kiếm theo số order
        order_layout = QHBoxLayout()
        self.order_number_input = QLineEdit()
        self.order_number_input.setPlaceholderText('Nhập số order để tìm kiếm')
        self.order_number_input.textChanged.connect(self.search_transactions)
        order_layout.addWidget(QLabel('Số Order:'))
        order_layout.addWidget(self.order_number_input)
        search_layout.addLayout(order_layout)
        
        # Phần lọc theo loại giao dịch
        type_layout = QHBoxLayout()
        self.transaction_type_combo = QComboBox()
        self.transaction_type_combo.addItems(['Tất cả', 'Mua', 'Bán'])
        self.transaction_type_combo.currentTextChanged.connect(self.search_transactions)
        type_layout.addWidget(QLabel('Loại:'))
        type_layout.addWidget(self.transaction_type_combo)
        search_layout.addLayout(type_layout)
        
        search_group.setLayout(search_layout)
        trade_layout.addWidget(search_group)
        
        # Bảng hiển thị giao dịch
        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(8)
        self.trade_table.setHorizontalHeaderLabels([
            'Loại', 'Số Order', 'Số tiền', 'Ngân hàng',
            'Số TK', 'Tên TK', 'Thông tin', 'Thời gian'
        ])
        
        # Căn chỉnh cột
        header = self.trade_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)  # Cột thời gian co giãn
        
        # Cho phép chọn một dòng
        self.trade_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.trade_table.setSelectionMode(QTableWidget.SingleSelection)
        self.trade_table.itemSelectionChanged.connect(self.on_trade_selection_change)
        
        trade_layout.addWidget(self.trade_table)
        
        # Phần nút thao tác
        button_layout = QHBoxLayout()
        
        self.view_qr_btn = QPushButton('Xem QR')
        self.view_qr_btn.clicked.connect(self.show_trade_qr)
        self.view_qr_btn.setEnabled(False)
        button_layout.addWidget(self.view_qr_btn)
        
        button_layout.addStretch()
        trade_layout.addLayout(button_layout)
        
        # Label hiển thị QR
        self.trade_qr_label = QLabel()
        self.trade_qr_label.setMinimumSize(300, 300)
        self.trade_qr_label.setAlignment(Qt.AlignCenter)
        self.trade_qr_label.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        self.trade_qr_label.hide()
        trade_layout.addWidget(self.trade_qr_label)

        # Tab xuất Excel
        excel_tab = QWidget()
        excel_layout = QVBoxLayout(excel_tab)
        
        # Phần chọn ngày
        date_layout = QHBoxLayout()
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-7))
        date_layout.addWidget(QLabel('Từ ngày:'))
        date_layout.addWidget(self.date_start)
        
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        date_layout.addWidget(QLabel('Đến ngày:'))
        date_layout.addWidget(self.date_end)
        
        excel_layout.addLayout(date_layout)
        
        # Nút xuất Excel
        self.export_excel_button = QPushButton('Xuất Excel')
        self.export_excel_button.clicked.connect(self.export_to_excel)
        excel_layout.addWidget(self.export_excel_button)
        
        # Thêm các tab
        self.tab_widget.addTab(main_tab, "Chính")
        self.tab_widget.addTab(trade_tab, "Giao dịch")
        self.tab_widget.addTab(excel_tab, "Xuất Excel")
        
    def show_transaction_viewer(self):
        """Mở giao diện xem giao dịch"""
        try:
            self.viewer = TransactionViewer()
            self.viewer.show()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không thể mở giao diện xem giao dịch: {str(e)}"
            )

    def create_order(self):
        """Tạo lệnh giao dịch mới"""
        try:
            # Lấy thông tin từ form
            trade_type = self.trade_type.currentText().lower()  # 'mua' hoặc 'bán'
            amount = int(self.amount_input.value())
            bank_name = self.bank_name.text().strip()
            account_number = self.account_number.text().strip()
            account_name = self.account_name.text().strip()
            message = self.message.text().strip()

            # Kiểm tra thông tin bắt buộc
            if not all([bank_name, account_number, account_name]):
                QMessageBox.warning(
                    self,
                    "Cảnh báo",
                    "Vui lòng nhập đầy đủ thông tin ngân hàng"
                )
                return

            # Tạo thông tin giao dịch
            transaction_info = {
                'type': trade_type,
                'amount': amount,
                'bank_name': bank_name,
                'account_number': account_number,
                'account_name': account_name,
                'message': message,
                'timestamp': int(datetime.now().timestamp())
            }

            # Lưu giao dịch
            order_number = self.transaction_storage.save_transaction(transaction_info)
            
            # Cập nhật giao diện
            self.generate_qr_button.setEnabled(True)
            self.log(f"✅ Đã tạo lệnh {trade_type.upper()} thành công")
            self.log(f"📝 Số lệnh: {order_number}")
            self.log(f"💰 Số tiền: {amount:,} VND")
            self.log(f"🏦 Ngân hàng: {bank_name}")
            self.log(f"📋 Số TK: {account_number}")
            self.log(f"👤 Tên TK: {account_name}")
            if message:
                self.log(f"💬 Nội dung: {message}")

            # Lưu thông tin giao dịch hiện tại
            self.p2p_instance.current_transaction = transaction_info
            self.p2p_instance.current_transaction['order_number'] = order_number

            # Xóa form
            self.clear_form()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không thể tạo lệnh: {str(e)}"
            )
            self.log(f"❌ Lỗi khi tạo lệnh: {str(e)}")

    def clear_form(self):
        """Xóa thông tin trong form"""
        self.amount_input.setValue(1000000)
        self.bank_name.clear()
        self.account_number.clear()
        self.account_name.clear()
        self.message.clear()

    def init_logging(self):
        self.log_handler = LogHandler()
        self.log_handler.log_signal.connect(self.append_log)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        self.log_handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        root_logger.setLevel(logging.INFO)

        self.logger = logging.getLogger("MyApp")
        self.logger.info("🚀 Ứng dụng khởi động")

    def append_log(self, msg):
        self.log_output.appendPlainText(msg)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def log(self, msg):
        self.logger.info(msg)

    def clear_log(self):
        self.log_output.clear()
        self.log("🗑️ Log đã được xóa")

    def handle_login(self):
        self.log("🔐 Đăng nhập...")
        self.label_login.setText("Đang đăng nhập...")
        self.login_button.setEnabled(False)

        self.login_thread = QThread()
        self.login_worker = Worker(login_app)
        self.login_worker.moveToThread(self.login_thread)

        self.login_thread.started.connect(self.login_worker.run)
        self.login_worker.finished.connect(self.login_success)
        self.login_worker.error.connect(self.login_failed)
        self.login_worker.finished.connect(self.login_thread.quit)
        self.login_worker.error.connect(self.login_thread.quit)
        self.login_worker.finished.connect(self.login_worker.deleteLater)
        self.login_worker.error.connect(self.login_worker.deleteLater)
        self.login_thread.finished.connect(self.login_thread.deleteLater)

        self.login_thread.start()

    def login_success(self):
        self.label_login.setText("Đăng nhập thành công!")
        self.login_button.setEnabled(True)
        self.log("✅ Đăng nhập thành công")

    def login_failed(self, err):
        self.label_login.setText("Đăng nhập thất bại!")
        self.login_button.setEnabled(True)
        self.log(f"❌ Lỗi: {err}")

    def handle_run_app(self):
        self.log("🚀 Chạy chương trình...")
        self.label_run_app.setText("Đang chạy...")
        self.run_button.setEnabled(False)
        self.login_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.run_thread = QThread()
        self.run_worker = Worker(self.p2p_instance.transactions_trading)
        self.run_worker.moveToThread(self.run_thread)

        self.run_thread.started.connect(self.run_worker.run)
        self.run_worker.finished.connect(self.run_success)
        self.run_worker.error.connect(self.run_failed)
        self.run_worker.finished.connect(self.run_thread.quit)
        self.run_worker.error.connect(self.run_thread.quit)
        self.run_worker.finished.connect(self.run_worker.deleteLater)
        self.run_worker.error.connect(self.run_worker.deleteLater)
        self.run_thread.finished.connect(self.run_thread.deleteLater)

        self.run_thread.start()

    def run_success(self):
        self.label_run_app.setText("Hoàn thành!")
        self.log("✅ Chạy xong")
        self.run_button.setEnabled(True)
        self.login_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def run_failed(self, err):
        self.label_run_app.setText("Lỗi!")
        self.log(f"❌ Lỗi: {err}")
        self.run_button.setEnabled(True)
        self.login_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def handle_stop(self):
        self.log("🛑 Dừng chương trình...")
        self.label_run_app.setText("Đã yêu cầu dừng")
        self.stop_button.setEnabled(False)
        self.run_button.setEnabled(True)
        self.login_button.setEnabled(True)

        if self.p2p_instance:
            self.p2p_instance.stop()

    def export_to_excel(self):
        """Xuất dữ liệu giao dịch ra file Excel"""
        try:
            # Lấy ngày bắt đầu và kết thúc từ date picker
            start_date = self.date_start.date().toPyDate()
            end_date = self.date_end.date().toPyDate()
            
            # Chuyển đổi sang timestamp
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            start_timestamp = int(start_dt.timestamp() * 1000)
            end_timestamp = int(end_dt.timestamp() * 1000)
            
            # Lấy dữ liệu giao dịch
            trades = self.p2p_instance.get_all_c2c_trades(
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp
            )
            
            if not trades:
                QMessageBox.warning(
                    self,
                    "Cảnh báo",
                    "Không có dữ liệu giao dịch trong khoảng thời gian đã chọn."
                )
                return
            
            # Chuyển đổi thành DataFrame
            df = pd.DataFrame(trades)
            
            # Lọc chỉ lấy giao dịch hoàn thành
            df = df[df['orderStatus'] == "COMPLETED"]
            
            # Chuyển đổi timestamp thành datetime
            df["createTime"] = pd.to_datetime(df["createTime"], unit="ms")
            df["createDay"] = df["createTime"].dt.date
            
            # Chuyển đổi kiểu dữ liệu số
            numeric_columns = ["totalPrice", "commission", "takerCommission"]
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            # Tính toán thống kê
            df_grouped = df.groupby(["createDay", "tradeType", "orderStatus"]).agg(
                totalPrice_sum=("totalPrice", "sum"),
                commission_sum=("commission", "sum"),
                takercommission_sum=("takerCommission", "sum")
            ).reset_index()
            
            # Hỏi người dùng nơi lưu file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Lưu file Excel",
                "",
                "Excel Files (*.xlsx)"
            )
            
            if file_path:
                # Xuất ra Excel
                with pd.ExcelWriter(file_path) as writer:
                    # Sheet tổng hợp
                    df_grouped.to_excel(writer, sheet_name="Tổng hợp", index=False)
                    
                    # Sheet chi tiết
                    df.to_excel(writer, sheet_name="Chi tiết", index=False)
                
                self.log(f"✅ Đã xuất dữ liệu ra file: {file_path}")
                QMessageBox.information(
                    self,
                    "Thành công",
                    f"Đã xuất dữ liệu ra file:\n{file_path}"
                )
            
        except Exception as e:
            error_msg = f"❌ Lỗi khi xuất Excel: {str(e)}"
            self.log(error_msg)
            QMessageBox.critical(
                self,
                "Lỗi",
                error_msg
            )

    def save_qr_image(self):
        """Lưu hình ảnh QR vào file"""
        if not hasattr(self, 'current_qr_path'):
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu mã QR",
            self.current_qr_path,
            "PNG Files (*.png);;All Files (*)"
        )
        
        if file_path:
            try:
                import shutil
                shutil.copy2(self.current_qr_path, file_path)
                self.log(f"✅ Đã lưu mã QR tại: {file_path}")
            except Exception as e:
                self.log(f"❌ Lỗi khi lưu mã QR: {str(e)}")
                QMessageBox.critical(self, "Lỗi", f"Không thể lưu mã QR: {str(e)}")

    def generate_qr(self):
        """Tạo mã QR cho giao dịch hiện tại"""
        try:
            # Kiểm tra xem có giao dịch hiện tại không
            if not self.p2p_instance.current_transaction:
                QMessageBox.warning(
                    self,
                    "Cảnh báo",
                    "Không có giao dịch nào đang được xử lý. Vui lòng đợi có giao dịch mới."
                )
                return

            tx = self.p2p_instance.current_transaction
            
            # Lấy thông tin từ giao dịch hiện tại
            amount = tx.get("amount", "1000000")
            account_number = tx.get("account_number", "")
            account_name = tx.get("account_name", "")
            bank_name = tx.get("bank_name", "")
            reference = tx.get("reference", "")
            order_number = tx.get("order_number", "")

            # Kiểm tra thông tin bắt buộc
            if not all([amount, account_number, account_name, bank_name]):
                QMessageBox.warning(
                    self,
                    "Cảnh báo",
                    "Thiếu thông tin cần thiết để tạo mã QR. Vui lòng kiểm tra lại giao dịch."
                )
                return

            # Tạo mã QR
            acqid_bank = get_bank_bin(bank_name)
            qr_image = generate_vietqr(
                accountno=account_number,
                accountname=account_name,
                acqid=acqid_bank,
                addInfo=reference or order_number,
                amount=amount,
                template="rc9Vk60"
            )

            # Hiển thị mã QR
            pixmap = QPixmap()
            pixmap.loadFromData(qr_image.getvalue())
            self.qr_label.setPixmap(pixmap.scaled(
                300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
            self.qr_label.setAlignment(Qt.AlignCenter)
            
            # Hiển thị thông tin giao dịch
            info_text = (
                f"Số tiền: {amount} VND\n"
                f"Ngân hàng: {bank_name}\n"
                f"Số tài khoản: {account_number}\n"
                f"Tên người nhận: {account_name}\n"
                f"Mã tham chiếu: {reference or order_number}"
            )
            self.transaction_info.setText(info_text)
            
            # Hiển thị nút lưu QR
            self.save_qr_button.setEnabled(True)
            
            # Log thông tin giao dịch
            self.log(f"Đã tạo mã QR cho giao dịch {order_number}")
            self.log(f"Thông tin giao dịch:\n{info_text}")

        except Exception as e:
            self.log(f"Lỗi khi tạo mã QR: {str(e)}")
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không thể tạo mã QR: {str(e)}"
            )

    def closeEvent(self, event):
        self.log("🔚 Đóng ứng dụng...")
        if self.p2p_instance:
            self.p2p_instance.stop()
        if self.login_thread:
            try:
                if self.login_thread.isRunning():
                    self.login_thread.quit()
                    self.login_thread.wait()
            except RuntimeError:
                pass  # Thread có thể đã bị delete

        if self.run_thread:
            try:
                if self.run_thread.isRunning():
                    self.run_thread.quit()
                    self.run_thread.wait()
            except RuntimeError:
                pass  # Thread có thể đã bị delete

        logging.getLogger().removeHandler(self.log_handler)
        event.accept()

    def search_transactions(self):
        """Tìm kiếm và hiển thị giao dịch từ file theo ngày"""
        try:
            # Lấy điều kiện tìm kiếm
            date = self.date_edit.date().toPyDate()
            order_number = self.order_number_input.text().strip()
            trade_type = self.transaction_type_combo.currentText()
            
            # Đọc dữ liệu từ file theo ngày
            transactions = []
            json_path = os.path.join('transactions', f'transactions_{date.strftime("%Y-%m-%d")}.json')
            
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    transactions = json.load(f)
                    self.log(f"✅ Đã load {len(transactions)} giao dịch từ file {json_path}")
            else:
                self.log(f"⚠️ Không tìm thấy giao dịch cho ngày {date.strftime('%d/%m/%Y')}")
                self.trade_table.setRowCount(0)
                return
            
            # Lọc theo điều kiện
            if order_number:
                transactions = [t for t in transactions if str(t.get('order_number', '')).startswith(order_number)]
                self.log(f"🔍 Đã lọc theo số order: {order_number}")
            
            if trade_type != 'Tất cả':
                # Chuyển đổi loại giao dịch từ giao diện sang dữ liệu
                type_map = {
                    'Mua': 'buy',
                    'Bán': 'sell'
                }
                target_type = type_map.get(trade_type)
                if target_type:
                    transactions = [t for t in transactions if t.get('type', '').lower() == target_type.lower()]
                    self.log(f"🔍 Đã lọc theo loại: {trade_type} (type={target_type})")
            
            # Hiển thị lên bảng
            self.trade_table.setRowCount(len(transactions))
            for row, trans in enumerate(transactions):
                # Loại giao dịch
                trans_type = trans.get('type', '').lower()
                display_type = "Mua" if trans_type == 'buy' else "Bán"
                self.trade_table.setItem(row, 0, QTableWidgetItem(display_type))
                
                # Số order
                self.trade_table.setItem(row, 1, QTableWidgetItem(
                    str(trans['order_number'])
                ))
                
                # Số tiền
                amount = f"{int(trans['amount']):,} VND"
                self.trade_table.setItem(row, 2, QTableWidgetItem(amount))
                
                # Ngân hàng
                self.trade_table.setItem(row, 3, QTableWidgetItem(
                    trans.get('bank_name', '')
                ))
                
                # Số tài khoản
                self.trade_table.setItem(row, 4, QTableWidgetItem(
                    trans.get('account_number', '')
                ))
                
                # Tên tài khoản
                self.trade_table.setItem(row, 5, QTableWidgetItem(
                    trans.get('account_name', '')
                ))
                
                # Thông tin thêm
                self.trade_table.setItem(row, 6, QTableWidgetItem(
                    trans.get('message', '')
                ))
                
                # Thời gian
                timestamp = trans.get('timestamp', 0)
                time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
                self.trade_table.setItem(row, 7, QTableWidgetItem(time_str))
                
                # Lưu đường dẫn QR vào item nếu có
                if 'qr_path' in trans:
                    self.trade_table.item(row, 1).setData(Qt.UserRole, trans['qr_path'])
            
            # Căn giữa các cột
            for row in range(self.trade_table.rowCount()):
                for col in range(self.trade_table.columnCount()):
                    item = self.trade_table.item(row, col)
                    if item:
                        item.setTextAlignment(Qt.AlignCenter)
            
            # Thông báo nếu không có giao dịch
            if not transactions:
                self.log(f"ℹ️ Không tìm thấy giao dịch nào phù hợp với điều kiện tìm kiếm")
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không thể tìm kiếm giao dịch: {str(e)}"
            )
            self.log(f"❌ Lỗi khi tìm kiếm giao dịch: {str(e)}")

    def on_trade_selection_change(self):
        """Xử lý khi chọn một dòng trong bảng giao dịch"""
        selected = self.trade_table.selectedItems()
        if selected:
            # Lấy đường dẫn QR từ dòng được chọn
            row = selected[0].row()
            qr_path = self.trade_table.item(row, 1).data(Qt.UserRole)
            self.view_qr_btn.setEnabled(bool(qr_path))
        else:
            self.view_qr_btn.setEnabled(False)
            self.trade_qr_label.hide()
            
    def show_trade_qr(self):
        """Hiển thị mã QR của giao dịch được chọn"""
        try:
            selected = self.trade_table.selectedItems()
            if not selected:
                return
                
            # Lấy đường dẫn QR
            row = selected[0].row()
            qr_path = self.trade_table.item(row, 1).data(Qt.UserRole)
            
            if not qr_path or not os.path.exists(qr_path):
                QMessageBox.warning(
                    self,
                    "Cảnh báo",
                    "Không tìm thấy file QR code"
                )
                return
                
            # Hiển thị QR
            pixmap = QPixmap(qr_path)
            scaled_pixmap = pixmap.scaled(
                300, 300,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.trade_qr_label.setPixmap(scaled_pixmap)
            self.trade_qr_label.show()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không thể hiển thị QR code: {str(e)}"
            )

    def clear_search(self):
        """Xóa tất cả điều kiện tìm kiếm và hiển thị lại tất cả giao dịch"""
        try:
            # Reset date về ngày hiện tại
            self.date_start.setDate(QDate.currentDate())
            
            # Xóa order number
            self.order_number_input.clear()
            
            # Reset transaction type về "All"
            self.transaction_type_combo.setCurrentText('Tất cả')
            
            # Lấy tất cả giao dịch và hiển thị
            transactions = self.p2p_instance.get_all_c2c_trades()
            if transactions:
                self.search_transactions()
                self.log("Đã xóa điều kiện tìm kiếm và hiển thị tất cả giao dịch")
            else:
                self.log("Không có giao dịch nào để hiển thị")
            
        except Exception as e:
            self.log(f"Lỗi khi xóa tìm kiếm: {str(e)}")
            QMessageBox.warning(self, "Lỗi", f"Không thể xóa tìm kiếm: {str(e)}")

    def on_tab_changed(self, index):
        """Xử lý khi chuyển tab"""
        tab_name = self.tab_widget.tabText(index)
        if tab_name == "Giao dịch":
            # Load dữ liệu khi chuyển đến tab giao dịch
            self.search_transactions()
            self.log("🔄 Đã tải lại dữ liệu giao dịch")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

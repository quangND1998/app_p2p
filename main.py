from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QPlainTextEdit, QFileDialog, QDateEdit, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QDate, QThread

import sys
import logging
from module.selenium_get_info import login_app, launch_chrome_remote_debugging
from module.binance_p2p import binance_p2p
from datetime import datetime
import tracemalloc
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

class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("P2P APP")
        self.login_thread = None
        self.run_thread = None
        self.p2p_instance = None
        self.chrome_thread = ChromeThread()
        self.init_ui()
        self.init_logging()


    def init_ui(self):
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

        self.export_excel_button = QPushButton("Xuất Excel")
        self.export_excel_button.setEnabled(True)  # Cho phép xuất Excel luôn
        self.export_excel_button.clicked.connect(self.export_excel)

        self.date_start = QDateEdit(calendarPopup=True)
        self.date_start.setDate(QDate.currentDate().addDays(-7))

        self.date_end = QDateEdit(calendarPopup=True)
        self.date_end.setDate(QDate.currentDate())

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(1000)

        self.generate_qr_button = QPushButton("Tạo QR")
        self.generate_qr_button.clicked.connect(self.generate_qr)

        layout = QVBoxLayout()
        for widget in [
            self.label_open, self.open_button,
            self.label_login, self.login_button,
            self.label_run_app, self.run_button, self.stop_button,
            self.clear_log_button, self.export_excel_button,
            QLabel("Từ ngày:"),self.date_start,
            QLabel("Đến ngày:"),self.date_end,
            QLabel("📜 Log Output:"), self.log_output,
            self.generate_qr_button
        ]:
            layout.addWidget(widget)
        self.setLayout(layout)
        self.resize(800, 600)

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

        self.p2p_instance = binance_p2p()
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

    def export_excel(self):
        try:
            start_qdate = self.date_start.date()
            end_qdate = self.date_end.date()
            start_dt = datetime(
                start_qdate.year(), start_qdate.month(), start_qdate.day(), 0, 0, 0
        )
            end_dt = datetime(
                end_qdate.year(), end_qdate.month(), end_qdate.day(), 23, 59, 59
            )
            # Đổi sang timestamp milliseconds
            start_timestamp = int(start_dt.timestamp() * 1000)
            end_timestamp = int(end_dt.timestamp() * 1000)
            
            df = binance_p2p().get_all_c2c_trades(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp
            )

            if df is None or df.empty:
                self.log("⚠️ DataFrame rỗng hoặc không có dữ liệu")
                return

            options = QFileDialog.Options()
            filename, _ = QFileDialog.getSaveFileName(self, "Lưu file Excel", "", "Excel Files (*.xlsx);;All Files (*)", options=options)
            if filename:
                if not filename.endswith(".xlsx"):
                    filename += ".xlsx"
                df.to_excel(filename, index=True)
                self.log(f"💾 Đã xuất file Excel: {filename}")

        except Exception as e:
            self.log(f"❌ Lỗi khi xuất file Excel: {e}")

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())

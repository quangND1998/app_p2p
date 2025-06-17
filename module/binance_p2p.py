import logging
import time
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
from config_env import BINANCE_KEY, BINANCE_SECRET
from module.generate_qrcode import generate_vietqr, get_nganhang_id

# from module.telegram_send_message import TelegramBot
from module.discord_send_message import DiscordBot
from module.selenium_get_info import extract_order_info, extract_info_by_key
import pandas as pd
from module.transaction_storage import TransactionStorage
from dotenv import load_dotenv
import os

# Load biến môi trường
load_dotenv()
BINANCE_KEY = os.getenv("BINANCE_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET")

logging.basicConfig(
    format="%(asctime)s  %(name)s  %(levelname)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class P2PBinance:
    def __init__(self, storage_dir: str = "transactions"):
        """
        Khởi tạo P2PBinance
        Args:
            storage_dir: Thư mục lưu trữ dữ liệu giao dịch
        """
        self._stop_flag = False
        self._running = False
        self.current_transaction = None
        self.logger = logging.getLogger("P2P")
        self.storage = TransactionStorage(storage_dir)

        # Khởi tạo Binance client
        try:
            self.logger.info(
                f"Initializing Binance client with key: {BINANCE_KEY[:5]}..."
            )
            self.client = Client(BINANCE_KEY, BINANCE_SECRET)
            self.logger.info("Binance client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Binance client: {e}")
            raise

    def handle_buy_order(self, order_number, message):
        """Xử lý đơn hàng mua"""
        infor_seller = extract_order_info(order_number)
        message = "".join(f"{k}: {v}\n" for k, v in infor_seller.items())

        infor_seller = extract_info_by_key(infor_seller)
        self.logger.debug(f"Extracted Info: {infor_seller}")

        fiat_amount = infor_seller.get("Fiat amount")
        full_name = infor_seller.get("Full Name")
        bank_card = infor_seller.get("Bank Card")
        bank_name = infor_seller.get("Bank Name")
        reference_message = infor_seller.get("Reference message")

        # Tạo thông tin giao dịch
        transaction_info = {
            "type": "buy",
            "order_number": order_number,
            "amount": fiat_amount,
            "bank_name": bank_name,
            "account_number": bank_card,
            "account_name": full_name,
            "reference": reference_message,
            "message": message,
        }

        if all([fiat_amount, bank_card, bank_name, reference_message, full_name]):
            acqid_bank = get_nganhang_id(bank_name)
            qr_image = generate_vietqr(
                accountno=bank_card,
                accountname=full_name,
                acqid=acqid_bank,
                addInfo=reference_message,
                amount=fiat_amount,
                template="rc9Vk60",
            )

            # Lưu thông tin giao dịch và mã QR
            qr_path = self.storage.save_transaction(transaction_info, qr_image)
            self.logger.info(f"Saved QR code to: {qr_path}")

            # Cập nhật thông tin giao dịch hiện tại
            self.current_transaction = transaction_info
            self.current_transaction["qr_path"] = qr_path

    def handle_sell_order(self, order_number, fiat_amount, message):
        """Xử lý đơn hàng bán"""
        qr_image = generate_vietqr(
            addInfo=order_number, amount=fiat_amount, template="rc9Vk60"
        )

        # Tạo thông tin giao dịch
        transaction_info = {
            "type": "sell",
            "order_number": order_number,
            "amount": fiat_amount,
            "message": message,
        }

        # Lưu thông tin giao dịch và mã QR
        qr_path = self.storage.save_transaction(transaction_info, qr_image)
        self.logger.info(f"Saved QR code to: {qr_path}")

        # Cập nhật thông tin giao dịch hiện tại
        self.current_transaction = transaction_info
        self.current_transaction["qr_path"] = qr_path

    def get_recent_transactions(self, limit: int = 10) -> list:
        """Lấy danh sách giao dịch gần đây"""
        return self.storage.get_recent_transactions(limit)

    def get_transaction(self, order_number: str) -> dict:
        """Lấy thông tin giao dịch theo mã đơn hàng"""
        return self.storage.get_transaction(order_number)

    def get_transactions_by_date(self, start_date: str, end_date: str) -> list:
        """Lấy danh sách giao dịch trong khoảng thời gian"""
        return self.storage.get_transactions_by_date(start_date, end_date)

    def transactions_trading(self):
        status = {
            "COMPLETED": "COMPLETED",
            "PENDING": "PENDING",
            "TRADING": "TRADING",
            "BUYER_PAYED": "BUYER PAYED",
            "DISTRIBUTING": "DISTRIBUTING",
            "IN_APPEAL": "IN APPEAL",
            "CANCELLED": "CANCELLED",
            "CANCELLED_BY_SYSTEM": "CANCELLED BY SYSTEM",
        }
        side = {"BUY": "BUY", "SELL": "SELL"}
        used_orders = {}
        err_count = 0

        self.startup_update(used_orders)

        while not self._stop_flag:
            try:
                for trade_type in ["BUY", "SELL"]:
                    end = int(datetime.utcnow().timestamp() * 1000)
                    start = end - 2700000  # ~45 minutes

                    result = self.get_c2c_trade_history(
                        tradeType=trade_type, startDate=start, endDate=end
                    )

                    for order in result["data"]:
                        order_status = order["orderStatus"]
                        order_number = order["orderNumber"]
                        previous_status = used_orders.get(order_number)
                        if order_status == "TRADING":
                            self.logger.info(
                                f"[Order] #{order_number} | Status: {order_status} | Type: {order['tradeType']} | "
                                f"Price: {order['fiatSymbol']}{order['unitPrice']} | "
                                f"Fiat Amount: {order['totalPrice']} {order['fiat']} | "
                                f"Crypto Amount: {order['amount']} {order['asset']} | "
                                f"Created at: {datetime.fromtimestamp(order['createTime']/1000).strftime('%Y-%m-%d %H:%M:%S')}"
                            )

                        if previous_status is None or previous_status != order_status:
                            message = (
                                f"Status: {status.get(order_status)}\n"
                                f"Type: {side.get(order['tradeType'])}\n"
                                f"Price: {order['fiatSymbol']}{order['unitPrice']}\n"
                                f"Fiat Amount: {float(order['totalPrice'])} {order['fiat']}\n"
                                f"Crypto Amount: {float(order['amount'])} {order['asset']}\n"
                                f"Order No.: {order_number}"
                            )

                            used_orders[order_number] = order_status
                            self._send_notification(message)

                            if order_status == "TRADING":
                                if trade_type == "BUY":
                                    self.handle_buy_order(order_number, message)
                                elif trade_type == "SELL":
                                    self.handle_sell_order(
                                        order_number,
                                        float(order["totalPrice"]),
                                        message,
                                    )

                time.sleep(1)

            except Exception as e:
                err_count += 1
                if err_count > 3:
                    self._running = False
                    self._send_notification(f"Error Count is {err_count}. Bot Stopped.")

    def stop(self):
        self._stop_flag = True
        logger.info("🛑 Yêu cầu dừng Binance P2P...")

    def get_c2c_trade_history(self, tradeType, startDate=None, endDate=None):
        """Lấy lịch sử giao dịch C2C"""
        try:
            return self.client.get_c2c_trade_history(
                tradeType=tradeType, startDate=startDate, endDate=endDate
            )
        except Exception as e:
            raise

    def _send_notification(self, message):
        """Gửi thông báo qua các kênh đã cấu hình"""
        try:
            if hasattr(self, "telegram_bot"):
                self.telegram_bot.send_message(message)
            if hasattr(self, "discord_bot"):
                self.discord_bot.send_message(message)
        except Exception as e:
            pass  # Bỏ qua lỗi khi gửi thông báo

    def get_all_c2c_trades(self, start_timestamp=None, end_timestamp=None):
        """Lấy tất cả giao dịch C2C trong khoảng thời gian và trả về DataFrame đã xử lý"""
        rows = 100
        all_trades = []

        if start_timestamp:
            start_timestamp = int(start_timestamp)
        if end_timestamp:
            end_timestamp = int(end_timestamp)

        for trade_type in ["BUY", "SELL"]:
            page = 1
            while True:
                params = {"tradeType": trade_type, "page": page, "rows": rows}
                if start_timestamp:
                    params["startTimestamp"] = start_timestamp
                if end_timestamp:
                    params["endTimestamp"] = end_timestamp

                try:
                    result = self.client.get_c2c_trade_history(**params)
                except BinanceAPIException as e:
                    break
                except Exception as e:
                    break

                trades = result.get("data", [])
                if trades:
                    all_trades.extend(trades)
                else:
                    break

                if page >= 100:
                    break

                page += 1

        if not all_trades:
            return pd.DataFrame()

        try:
            # Chuyển đổi thành DataFrame
            df = pd.json_normalize(all_trades)

            # Lọc chỉ lấy giao dịch hoàn thành
            df = df[df["orderStatus"] == "COMPLETED"]

            if df.empty:
                return pd.DataFrame()

            # Xử lý thời gian
            df["createTime"] = pd.to_datetime(df["createTime"], unit="ms")
            df["createDay"] = df["createTime"].dt.date

            # Chuyển đổi kiểu dữ liệu số
            numeric_columns = ["totalPrice", "commission", "takerCommission"]
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # Groupby và tính tổng
            df_grouped = (
                df.groupby(["createDay", "tradeType", "orderStatus"])
                .agg(
                    totalPrice_sum=("totalPrice", "sum"),
                    commission_sum=("commission", "sum"),
                    takercommission_sum=("takerCommission", "sum"),
                )
                .reset_index()
            )

            return df_grouped

        except Exception as e:
            return pd.DataFrame()

    def thongke_today(self):
        all_data = []
        try:
            for trd in ["BUY", "SELL"]:
                res = self.client.get_c2c_trade_history(
                    tradeType=trd,
                )
                logger.debug(f"Trade History Result for {trd}: {res}")
                if res.get("data"):
                    all_data.extend(res["data"])

            if not all_data:
                logger.info("No trade data found for today.")
                return pd.DataFrame()

            df = pd.json_normalize(all_data)
            df["createTime"] = df["createTime"].apply(
                lambda x: datetime.fromtimestamp(x / 1000).strftime("%Y-%m-%d %H:%M:%S")
            )
            df["createDay"] = pd.to_datetime(
                df["createTime"], format="%Y-%m-%d %H:%M:%S"
            ).dt.date
            today = datetime.utcnow().date()
            # df_today = df[df["createDay"] == today]
            df_today = df
            df_today = df_today[
                [
                    "createDay",
                    "tradeType",
                    "orderStatus",
                    "totalPrice",
                    "unitPrice",
                    "commission",
                ]
            ]
            df_today["totalPrice"] = df_today["totalPrice"].astype(float)
            df_today["commission"] = df_today["commission"].astype(float)
            df_today = (
                df_today.groupby(["createDay", "tradeType", "orderStatus"])
                .agg({"totalPrice": ["sum"], "commission": ["sum"]})
                .reset_index()
            )
        except Exception as e:
            logger.error(f"Error in thongke_today: {e}", exc_info=True)
            df_today = pd.DataFrame()
        return df_today

    def startup_update(self, database: dict):
        for trd in ["BUY", "SELL"]:
            res = self.get_c2c_trade_history(tradeType=trd)
            logger.debug(f"Startup Trade History Result: {res}")
            for k in res["data"]:
                database[k["orderNumber"]] = k["orderStatus"]

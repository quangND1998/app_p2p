import logging
import time
from datetime import datetime
from binance import Client
from binance.exceptions import BinanceAPIException
from config_env import BINANCE_KEY, BINANCE_SECRET
from module.generate_qrcode import generate_vietqr,get_nganhang_id
# from module.telegram_send_message import TelegramBot
from module.discord_send_message import DiscordBot
from module.selenium_get_info import extract_order_info,extract_info_by_key
import pandas as pd

logging.basicConfig(format='%(asctime)s  %(name)s  %(levelname)s: %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class binance_p2p:
    def __init__(self):
        self.client = Client(BINANCE_KEY, BINANCE_SECRET)
        # self.telegram_bot = TelegramBot(token=None)  # Initialize the Telegram bot with the token from config_env
        self.discord_bot = DiscordBot(webhook_url=None)
        self._stop_flag = False
        self.logger = logging.getLogger("P2P")

    def stop(self):
        self._stop_flag = True
        logger.info("🛑 Yêu cầu dừng Binance P2P...")

    def get_c2c_trade_history(self, tradeType, startDate=None, endDate=None):
        return self.client.get_c2c_trade_history(tradeType=tradeType, startDate=startDate, endDate=endDate)
    
    def get_all_c2c_trades(self, start_timestamp=None, end_timestamp=None):
        rows = 100
        all_trades = []

        if start_timestamp:
            start_timestamp = int(start_timestamp)
        if end_timestamp:
            end_timestamp = int(end_timestamp)

        for trade_type in ["BUY", "SELL"]:
            page = 1
            while True:
                params = {
                    "tradeType": trade_type,
                    "page": page,
                    "rows": rows
                }
                if start_timestamp:
                    params["startTimestamp"] = start_timestamp
                if end_timestamp:
                    params["endTimestamp"] = end_timestamp
                print(params)
                try:
                    result = self.client.get_c2c_trade_history(**params)
                except BinanceAPIException as e:
                    print(f"[Lỗi API] {e.message}")
                    break

                trades = result.get("data", [])
                all_trades.extend(trades)

                if not trades:
                    print(f"[{trade_type}] Hết dữ liệu tại trang {page}")
                    break

                if page >= 100:
                    print(f"[{trade_type}] Vượt quá giới hạn trang (100)")
                    break

                page += 1
        if not all_trades:
            print("Không có giao dịch nào.")
            return pd.DataFrame()
        print(all_trades)
        df = pd.json_normalize(all_trades)
        df = df[df['orderStatus'] == "COMPLETED"]
        df["createTime"] = pd.to_datetime(df["createTime"], unit="ms")
        df["createDay"] = df["createTime"].dt.date
        # Chuyển đổi kiểu dữ liệu
        df["totalPrice"] = pd.to_numeric(df["totalPrice"], errors="coerce")
        df["commission"] = pd.to_numeric(df["commission"], errors="coerce")
        df["takerCommission"] = pd.to_numeric(df["takerCommission"], errors="coerce")
        df_grouped = df.groupby(["createDay", "tradeType", "orderStatus"]).agg(
                                                                                totalPrice_sum=("totalPrice", "sum"),
                                                                                commission_sum=("commission", "sum"),
                                                                                takercommission_sum=("takerCommission", "sum")
                                                                                ).reset_index()
        return df_grouped
    
    def thongke_today(self):
        all_data = []
        try:
            for trd in ["BUY", "SELL"]:
                res = self.client.get_c2c_trade_history(tradeType=trd,)
                logger.debug(f'Trade History Result for {trd}: {res}')
                if res.get('data'):
                    all_data.extend(res['data'])
            
            if not all_data:
                logger.info("No trade data found for today.")
                return pd.DataFrame()  
            
            df = pd.json_normalize(all_data)
            df["createTime"] = df["createTime"].apply(
                lambda x: datetime.fromtimestamp(x / 1000).strftime('%Y-%m-%d %H:%M:%S')
            )
            df["createDay"] = pd.to_datetime(df["createTime"], format='%Y-%m-%d %H:%M:%S').dt.date
            today = datetime.utcnow().date()
            # df_today = df[df["createDay"] == today]
            df_today = df
            df_today= df_today[["createDay", "tradeType", "orderStatus", "totalPrice","unitPrice","commission"]]
            df_today["totalPrice"] = df_today["totalPrice"].astype(float)
            df_today["commission"] = df_today["commission"].astype(float)
            df_today = df_today.groupby(["createDay", "tradeType", "orderStatus"]) \
                            .agg({"totalPrice": ["sum"],"commission": ["sum"]}) \
                            .reset_index()
        except Exception as e:
            logger.error(f"Error in thongke_today: {e}", exc_info=True)
            df_today = pd.DataFrame() 
        return df_today
    
    def startup_update(self, database: dict):
        for trd in ["BUY", "SELL"]:
            res = self.get_c2c_trade_history(tradeType=trd)
            logger.debug(f'Startup Trade History Result: {res}')
            for k in res['data']:
                database[k['orderNumber']] = k['orderStatus']

    def handle_buy_order(self, order_number, message):
        infor_seller = extract_order_info(order_number)
        message = ''.join(f"{k}: {v}\n" for k, v in infor_seller.items())
        # self.telegram_bot.send_message(
        #     f"""<b>🔔 [Thông báo]!</b>
        #         <b>Thông tin người bán:</b>
        #         {message}
        #         <b>Đối chiếu với QR code bên dưới!</b>""",
        #             parse_mode="HTML"
        #         )
        self.discord_bot.send_message(
            f"""**🔔 [Thông báo]!**
                **Thông tin người bán:**
                {message}
                **Đối chiếu với QR code bên dưới!**"""
                )
        infor_seller = extract_info_by_key(infor_seller)
        
        logger.debug(f'Extracted Info: {infor_seller}')
        
        fiat_amount = infor_seller.get("Fiat amount")
        full_name = infor_seller.get("Full Name")
        bank_card = infor_seller.get("Bank Card")
        bank_name = infor_seller.get("Bank Name")
        reference_message = infor_seller.get("Reference message")

        if all([fiat_amount, bank_card, bank_name, reference_message, full_name]):
            acqid_bank = get_nganhang_id(bank_name)
            image = generate_vietqr(
                accountno=bank_card,
                accountname=full_name,
                acqid=acqid_bank,
                addInfo=reference_message,
                amount=fiat_amount,
                template="rc9Vk60"
            )
            # self.telegram_bot.send_photo(image, message)
            self.discord_bot.send_photo(image, message)
            


    def handle_sell_order(self, order_number, fiat_amount, message):
        image = generate_vietqr(
            addInfo=order_number,
            amount=fiat_amount,
            template="rc9Vk60"
        )
        # self.telegram_bot.send_photo(image, message)
        self.discord_bot.send_photo(image, message)

    
    def transactions_trading(self):
        self.logger.info("🚀 Bắt đầu chạy giao dịch P2P")
        status = {
            "COMPLETED": "COMPLETED",
            "PENDING": "PENDING",
            "TRADING": "TRADING",
            "BUYER_PAYED": "BUYER PAYED",
            "DISTRIBUTING": "DISTRIBUTING",
            "IN_APPEAL": "IN APPEAL",
            "CANCELLED": "CANCELLED",
            "CANCELLED_BY_SYSTEM": "CANCELLED BY SYSTEM"
        }
        side = {"BUY": "BUY", "SELL": "SELL"}
        used_orders = {}
        err_count = 0
        link = "https://p2p.binance.com/en/fiatOrderDetail?orderNo="

        logger.info('Bot Started P2P Order Tracking for Last 45 Minutes Only.')
        self.startup_update(used_orders)

        while not self._stop_flag:
            try:
                for trade_type in ["BUY", "SELL"]:
                    end = int(datetime.utcnow().timestamp() * 1000)
                    start = end - 2700000  # ~45 minutes
                    logger.debug(f'Start timestamp: {start}, End timestamp: {end}')

                    result = self.get_c2c_trade_history(tradeType=trade_type, startDate=start, endDate=end)
                    logger.debug(f'Trade History Result: {result}')

                    for order in result['data']:
                        order_status = order['orderStatus']
                        order_number = order['orderNumber']
                        previous_status = used_orders.get(order_number)

                        is_new_order = previous_status is None
                        is_status_changed = previous_status != order_status

                        if is_new_order or is_status_changed:
                            logger.info(f"New Update:- Order No.: {order_number} | Status: {order_status}")

                            message = (
                                f"Status: {status.get(order_status)}\n"
                                f"Type: {side.get(order['tradeType'])}\n"
                                f"Price: {order['fiatSymbol']}{order['unitPrice']}\n"
                                f"Fiat Amount: {float(order['totalPrice'])} {order['fiat']}\n"
                                f"Crypto Amount: {float(order['amount'])} {order['asset']}\n"
                                f"Order No.: <a href='{link}{order_number}'>{order_number}</a>"
                            )

                            used_orders[order_number] = order_status
                            logger.info("SENDING TO TELEGRAM")
                            # self.telegram_bot.send_message(message)
                            self.discord_bot.send_message(message)

                            if order_status == "TRADING":
                                if trade_type == "BUY":
                                    self.handle_buy_order(order_number, message)
                                elif trade_type == "SELL":
                                    self.handle_sell_order(order_number, float(order['totalPrice']), message)
                time.sleep(1)

            except Exception as e:
                logger.error(f'{e}', exc_info=True)
                err_count += 1

                if err_count > 3:
                    self._running = False
                    logger.warning(f"Error Count is {err_count}. Bot Stopped.")
                    # self.telegram_bot.send_message(f"Error Count is {err_count}. Bot Stopped.")
                    self.discord_bot.send_message(f"Error Count is {err_count}. Bot Stopped.")



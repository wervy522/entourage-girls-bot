from flask import Flask, request, jsonify
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка конфигурации
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

LAVA_API_KEY = config['LAVA_API_KEY']
GOOGLE_SHEET_NAME = config['GOOGLE_SHEET_NAME']

# Настройка доступа к Google Sheets
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(credentials)
sheet = gc.open(GOOGLE_SHEET_NAME).sheet1

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка вебхуков от Lava Top"""
    try:
        # Получаем данные из вебхука
        data = request.json
        logger.info(f"Получен вебхук: {data}")
        
        # Проверяем статус платежа
        if data.get('status') == 'success':
            # Получаем данные пользователя из custom_fields
            custom_fields = data.get('custom_fields', {})
            user_id = custom_fields.get('user_id')
            username = custom_fields.get('username')
            
            if user_id and username:
                # Обновляем статус в Google таблице
                try:
                    # Ищем строку с telegram пользователя
                    cell = sheet.find(username)
                    if cell:
                        # Обновляем статус
                        sheet.update_cell(cell.row, sheet.find('Статус').col, 'Оплачено')
                        logger.info(f"Статус обновлен для пользователя {username}")
                        return jsonify({'status': 'success'}), 200
                except gspread.exceptions.CellNotFound:
                    logger.error(f"Пользователь {username} не найден в таблице")
                    return jsonify({'status': 'error', 'message': 'User not found'}), 404
                
        return jsonify({'status': 'error', 'message': 'Invalid payment status'}), 400
        
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 
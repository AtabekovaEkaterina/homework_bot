import json
import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from telegram import Bot, TelegramError

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('practicum_token')
TELEGRAM_TOKEN = os.getenv('telegram_token')
TELEGRAM_CHAT_ID = os.getenv('telegram_chat_id')

RETRY_TIME = 600
ENDPOINT = ''
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramError as e:
        logger.error(f'Сбой при отправке сообщения в Telegram: {e}')
    except Exception as e:
        logger.error(f'Сбой при отправке сообщения в Telegram: {e}')
    else:
        logger.info('Сообщение успешно отправлено')


def get_api_answer(current_timestamp):
    """Функция создания запроса к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except ValueError:
        logger.error(
            'Переменная response не найдена'
        )
        raise
    except requests.ConnectionError as e:
        logger.error(
            f'Эндпоинт недоступен: произошла ошибка подключения: {e}'
        )
        raise
    except requests.ReadTimeout as e:
        logger.error(
            f'Эндпоинт недоступен: данные не получены за отведенное время: {e}'
        )
        raise
    except requests.Timeout as e:
        logger.error(
            f'Эндпоинт недоступен: время запроса истекло: {e}'
        )
        raise
    except requests.RequestException as e:
        logger.error(
            f'Эндпоинт недоступен: произошло неоднозначное исключение: {e}'
        )
        raise
    if response.status_code != HTTPStatus.OK:
        raise exceptions.HTTPErrorException(
            'Эндпоинт недоступен: запрос не вернул статус 200'
        )
    try:
        response = response.json()
    except json.decoder.JSONDecodeError:
        logger.error('Ответ API не преобразован в json')
    return response


def check_response(response):
    """Функция проверки ответа API на корректность."""
    try:
        homework = response['homeworks']
    except KeyError:
        logger.error('ключ homeworks отсутствует')
        raise
    if not isinstance(response, dict):
        logger.error(
            'Ответ API некорректностый: response не возвращает словарь'
        )
        raise TypeError(
            'Ответ API некорректностый: response не возвращает словарь'
        )
    if not isinstance(homework, list):
        logger.error(
            'Ответ API некорректностый: значние homework не список'
        )
        raise ValueError(
            'Ответ API некорректностый: значние homework не список'
        )
    return homework


def parse_status(homework):
    """Функция извлечения статуса домашней работы."""
    homework_name = homework.get('homework_name')
    if homework is None and len(homework_name) == 0:
        raise ValueError(
            'Получено некорректное значение homework_name'
        )
    homework_status = homework.get('status')
    if homework_status is None and len(homework_status) == 0:
        raise ValueError(
            'Получено некорректное значение status'
        )
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError('Не найдено возможное значение статуса')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Функция проверки доступности переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        if token is None:
            logger.critical(
                'Отсутствует обязательная переменная окружения'
            )
            return False
    return True


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if len(homework) > 0:
                message = parse_status(homework[0])
                send_message(bot, message)
            current_timestamp = int(time.time()) - RETRY_TIME
            time.sleep(RETRY_TIME)
        except Exception as e:
            message = f'Сбой в работе программы: {e}'
            logger.critical(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()

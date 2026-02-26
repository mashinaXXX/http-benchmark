# HTTP Server Benchmark Tool

Утилита для тестирования доступности HTTP серверов и измерения времени ответа.

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/mashinaXXX/http-benchmark.git
cd http-benchmark
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

## Использование

### Основные параметры:
```bash
python benchmark.py -H https://example.com,https://google.com -C 5
```

### Параметры:
| Параметр | Описание |
|----------|----------|
| `-H`, `--hosts` | Список URL через запятую |
| `-F`, `--file`  | Файл со списком URL (по одному на строку) |
| `-C`, `--count` | Количество запросов (по умолчанию: 1) |
| `-O`, `--output`| Файл для сохранения результатов |

### Пример вывода:
```
[https://example.com]
  Успешно: 5
  Ошибки: 0 (сервер) / 0 (соединение)
  Время: min=0.245s, max=0.512s, avg=0.324s

[https://google.com]
  Успешно: 5
  Ошибки: 0 (сервер) / 0 (соединение)
  Время: min=0.112s, max=0.231s, avg=0.154s
```

## Примеры

1. Тестирование из командной строки:
```bash
python benchmark.py -H https://ya.ru,https://google.com -C 10
```

2. Использование файла с URL:
```bash
python benchmark.py -F urls.txt -C 3 -O results.txt
```

3. Пример файла urls.txt:
```
https://example.com
https://google.com
https://github.com
```

## Требования
- Python 3.8+
- Библиотека aiohttp 3.8.0+
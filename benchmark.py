import argparse
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import sys


class ServerBenchmark:
    def __init__(self):
        self.results = []

    def test_server(self, url, requests_count=1):
        """Тестирует один сервер"""
        stats = {
            'url': url,
            'success': 0,
            'failed': 0,
            'errors': 0,
            'times': []
        }

        for _ in range(requests_count):
            try:
                start = time.time()
                response = requests.get(url, timeout=5)
                elapsed = time.time() - start

                if response.ok:
                    stats['success'] += 1
                    stats['times'].append(elapsed)
                else:
                    stats['failed'] += 1
            except requests.exceptions.RequestException:
                stats['errors'] += 1

        # Расчет статистики
        if stats['times']:
            stats['min'] = min(stats['times'])
            stats['max'] = max(stats['times'])
            stats['avg'] = sum(stats['times']) / len(stats['times'])
        else:
            stats['min'] = stats['max'] = stats['avg'] = 0

        return stats

    def run_benchmark(self, servers, requests_count=1):
        """Запускает тестирование для списка серверов"""
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.test_server, server, requests_count)
                       for server in servers]

            for future in as_completed(futures):
                self.results.append(future.result())

        return self.results


def validate_url(url):
    """Проверяет валидность URL"""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except ValueError:
        return False


def parse_args():
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(
        description='HTTP Server Benchmark Tool',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-H', '--hosts', help='Список URL через запятую')
    group.add_argument('-F', '--file', help='Файл со списком URL')

    parser.add_argument('-C', '--count', type=int, default=1,
                        help='Количество запросов на сервер')
    parser.add_argument('-O', '--output', help='Файл для сохранения результатов')

    return parser.parse_args()


def read_urls_from_file(filename):
    """Читает URL из файла"""
    try:
        with open(filename, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except IOError as e:
        raise ValueError(f"Ошибка чтения файла: {e}")


def format_results(results):
    """Форматирует результаты для вывода"""
    report = []
    for res in results:
        report.append(f"[{res['url']}]")
        report.append(f"  Успешно: {res['success']}")
        report.append(f"  Ошибки: {res['failed']} (сервер) / {res['errors']} (соединение)")
        report.append(f"  Время: min={res['min']:.3f}s, max={res['max']:.3f}s, avg={res['avg']:.3f}s")
        report.append("")
    return "\n".join(report)


def main():
    try:
        args = parse_args()

        # Получаем список URL
        if args.hosts:
            urls = [u.strip() for u in args.hosts.split(',')]
        else:
            urls = read_urls_from_file(args.file)

        # Валидация URL
        invalid_urls = [u for u in urls if not validate_url(u)]
        if invalid_urls:
            raise ValueError(f"Невалидные URL: {', '.join(invalid_urls)}")

        if args.count < 1:
            raise ValueError("Количество запросов должно быть ≥ 1")

        # Запускаем тестирование
        benchmark = ServerBenchmark()
        results = benchmark.run_benchmark(urls, args.count)

        # Выводим результаты
        report = format_results(results)

        if args.output:
            try:
                with open(args.output, 'w') as f:
                    f.write(report)
                print(f"Результаты сохранены в {args.output}")
            except IOError:
                print("Ошибка сохранения результатов", file=sys.stderr)
                print(report)
        else:
            print(report)

    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

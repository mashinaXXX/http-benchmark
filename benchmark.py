import argparse
import asyncio
import aiohttp
import time
from urllib.parse import urlparse
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional


class AsyncServerBenchmark:
    def __init__(self):
        self.results = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=5, connect=3)

    async def test_server(self, url: str, requests_count: int,
                          global_sem: asyncio.Semaphore,
                          server_sem: asyncio.Semaphore) -> Dict[str, Any]:
        """Асинхронно тестирует один сервер с двумя уровнями ограничений"""
        stats = {
            'url': url,
            'success': 0,
            'failed': 0,
            'errors': 0,
            'times': []
        }

        async with global_sem:
            async with server_sem:
                tasks = [self._make_request(url, stats) for _ in range(requests_count)]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for r in results:
                    if isinstance(r, Exception) and not isinstance(r, (KeyboardInterrupt, asyncio.CancelledError)):
                        stats['errors'] += 1

        if stats['times']:
            stats['min'] = min(stats['times'])
            stats['max'] = max(stats['times'])
            stats['avg'] = sum(stats['times']) / len(stats['times'])
            variance = sum((t - stats['avg']) ** 2 for t in stats['times']) / len(stats['times'])
            stats['std_dev'] = variance ** 0.5
        else:
            stats['min'] = stats['max'] = stats['avg'] = stats['std_dev'] = 0

        return stats

    async def _make_request(self, url: str, stats: Dict[str, Any]) -> None:
        """Выполняет один асинхронный запрос"""
        try:
            start = time.time()
            async with self.session.get(url, timeout=self.timeout) as response:
                await response.read()
                elapsed = time.time() - start

                if 200 <= response.status < 300:
                    stats['success'] += 1
                    stats['times'].append(elapsed)
                else:
                    stats['failed'] += 1

        except asyncio.TimeoutError:
            stats['errors'] += 1
        except aiohttp.ClientConnectionError:
            stats['errors'] += 1
        except aiohttp.ClientError:
            stats['errors'] += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            stats['errors'] += 1

    async def run_benchmark(self, servers: List[str], requests_count: int = 1,
                            max_concurrent: int = 10, per_server_limit: int = 3,
                            global_timeout: int = 300) -> List[Dict[str, Any]]:
        """Запускает асинхронное тестирование для списка серверов"""
        connector = aiohttp.TCPConnector(
            limit=100, limit_per_host=per_server_limit,
            ttl_dns_cache=300, enable_cleanup_closed=True
        )

        timeout = aiohttp.ClientTimeout(total=5, connect=3, sock_read=5)

        try:
            async with aiohttp.ClientSession(
                    timeout=timeout, connector=connector,
                    headers={'User-Agent': 'HTTP-Benchmark/1.0'}
            ) as session:
                self.session = session
                global_semaphore = asyncio.Semaphore(max_concurrent)

                tasks = []
                for server in servers:
                    server_semaphore = asyncio.Semaphore(per_server_limit)
                    tasks.append(self.test_server(server, requests_count,
                                                  global_semaphore, server_semaphore))

                self.results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=global_timeout
                )

        except asyncio.TimeoutError:
            print("\nПревышено общее время выполнения", file=sys.stderr)
        except Exception as e:
            print(f"\nКритическая ошибка: {e}", file=sys.stderr)

        return self.results


def validate_url(url: str) -> bool:
    """Проверяет валидность URL"""
    try:
        result = urlparse(url)
        return result.scheme in ['http', 'https'] and result.netloc and '.' in result.netloc
    except (ValueError, AttributeError):
        return False


def parse_args():
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(
        description='Async HTTP Server Benchmark Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Примеры:\n  python bench.py -H https://ya.ru,https://google.com -C 10\n  python bench.py -F urls.txt -C 20 -P 15 -O results.txt"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-H', '--hosts', help='Список URL через запятую')
    group.add_argument('-F', '--file', help='Файл со списком URL')

    parser.add_argument('-C', '--count', type=int, default=1, help='Количество запросов на сервер')
    parser.add_argument('-O', '--output', help='Файл для сохранения результатов')
    parser.add_argument('-P', '--parallel', type=int, default=10, help='Максимум параллельных запросов')
    parser.add_argument('--per-server', type=int, default=3, help='Лимит на сервер')
    parser.add_argument('--timeout', type=int, default=300, help='Общий таймаут (сек)')
    parser.add_argument('--no-color', action='store_true', help='Отключить цветной вывод')

    return parser.parse_args()


def read_urls_from_file(filename: str) -> List[str]:
    """Читает URL из файла"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
            if not urls:
                raise ValueError("Файл не содержит URL адресов")
            return urls
    except (FileNotFoundError, IOError) as e:
        raise ValueError(f"Ошибка чтения файла: {e}")


def format_results(results: List[Dict[str, Any]], use_color: bool = True) -> str:
    """Форматирует результаты для вывода"""
    colors = {
        'reset': '\033[0m', 'bold': '\033[1m', 'green': '\033[92m',
        'yellow': '\033[93m', 'red': '\033[91m', 'blue': '\033[94m', 'cyan': '\033[96m'
    }

    def c(code, text):
        return f"{colors[code]}{text}{colors['reset']}" if use_color else text

    valid_results = [r for r in results if isinstance(r, dict)]
    errors = [str(r) for r in results if isinstance(r, Exception)]

    if not valid_results:
        return f"\n{c('red', 'Нет результатов для отображения')}\n"

    # Заголовок
    report = [
        f"\n{c('bold', '=' * 60)}",
        f"{c('cyan', 'HTTP SERVER BENCHMARK RESULTS')}",
        f"{c('bold', '=' * 60)}",
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ""
    ]

    # Ошибки (если есть)
    if errors:
        report.append(f"{c('yellow', f'Ошибки: {len(errors)}')}")
        for e in errors[:2]:
            report.append(f"\t{c('red', '•')} {e[:100]}...")
        if len(errors) > 2:
            report.append(f"\t{c('yellow', f'... и еще {len(errors) - 2}')}")
        report.append("")

    # Результаты
    for i, res in enumerate(sorted(valid_results, key=lambda x: x['avg']), 1):
        total = res['success'] + res['failed'] + res['errors']
        rate = (res['success'] / total * 100) if total > 0 else 0
        color = 'green' if rate == 100 else 'yellow' if rate >= 80 else 'red'

        report.append(f"{c('bold', f'#{i}')} {c('blue', res['url'])}")
        report.append(f"  {c('bold', '├─')} {c(color, str(res['success']))}/{total} ({rate:.1f}%) | "
                      f"{res['failed']} | {res['errors']}")
        report.append(f"  {c('bold', '└─')} min={res['min']:.3f}s max={res['max']:.3f}s "
                      f"avg={c('cyan', f'{res["avg"]:.3f}')}s σ={res['std_dev']:.3f}s")
        report.append("")

    return "\n".join(report)


async def main_async():
    """Асинхронная main функция"""
    try:
        args = parse_args()

        # Получение URL
        urls = [u.strip() for u in args.hosts.split(',') if u.strip()] if args.hosts else read_urls_from_file(args.file)

        if not urls:
            raise ValueError("Нет URL для тестирования")

        # Валидация
        valid_urls = [u for u in urls if validate_url(u)]
        invalid_count = len(urls) - len(valid_urls)

        if invalid_count:
            print(f"Пропущено {invalid_count} невалидных URL", file=sys.stderr)

        if not valid_urls:
            raise ValueError("Нет валидных URL для тестирования")

        # Проверка параметров
        if args.count < 1 or args.parallel < 1 or args.per_server < 1:
            raise ValueError("Параметры count, parallel и per-server должны быть ≥ 1")

        # Заглушка прогресса
        print(f"\nТестирование {len(valid_urls)} серверов ({args.count} запросов на сервер) | "
              f"⚡ {args.parallel} параллельных | {args.timeout}с ... ", end='', flush=True)

        # Запуск
        start_time = time.time()
        benchmark = AsyncServerBenchmark()
        results = await benchmark.run_benchmark(
            valid_urls, args.count, args.parallel, args.per_server, args.timeout
        )
        elapsed = time.time() - start_time

        print(f"{elapsed:.1f}с")

        # Форматирование результатов
        report = format_results(results, not args.no_color)
        report += f"\n{'─' * 60}\nВсего: {elapsed:.2f}с | "
        report += f"{sum(1 for r in results if isinstance(r, dict))}/{len(valid_urls)} серверов\n"

        # Вывод/сохранение
        if args.output:
            clean_report = format_results(results, False) + f"\n{'─' * 60}\nTotal: {elapsed:.2f}s"
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(clean_report)
            print(f"Результаты сохранены в {args.output}")

        print(report)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\nПрервано пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\nОшибка: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Точка входа"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

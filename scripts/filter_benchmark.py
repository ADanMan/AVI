#!/usr/bin/env python3
"""
Интерактивный скрипт для прогона датасета с вопросами через фильтр AVI.

Позволяет:
- Загрузить CSV с вопросами
- Выбрать колонку с текстом для фильтрации
- Прогнать все вопросы через фильтр
- Сохранить результаты с метаданными и конфигурацией фильтра

Использование:
    python scripts/filter_benchmark.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from tqdm import tqdm

try:
    import httpx
except ImportError:
    httpx = None

from config.settings import settings
from src.core.content_filter import ContentFilterService
from src.services.vector_db import VectorDBService
from src.utils.logger import logger


def print_header(text: str):
    """Печать заголовка."""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}\n")


def print_columns(df: pd.DataFrame):
    """Показать доступные колонки."""
    print("\nДоступные колонки в файле:\n")
    for idx, col in enumerate(df.columns, 1):
        sample = df[col].iloc[0] if len(df) > 0 else "н/д"
        # Обрезаем длинные значения
        sample_str = str(sample)[:60] + "..." if len(str(sample)) > 60 else str(sample)
        print(f"  {idx}. {col:30} | Пример: {sample_str}")
    print()


def select_column(df: pd.DataFrame, prompt: str) -> str:
    """Интерактивный выбор колонки."""
    while True:
        choice = input(prompt).strip()

        # Попробовать как номер
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(df.columns):
                return df.columns[idx]
            else:
                print(f"❌ Неверный номер. Выберите от 1 до {len(df.columns)}")
                continue

        # Попробовать как название
        if choice in df.columns:
            return choice

        print(f"❌ Колонка '{choice}' не найдена. Попробуйте еще раз.")


def get_text_input(prompt: str, default: str = "") -> str:
    """Получить текстовый ввод с значением по умолчанию."""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def get_bool_input(prompt: str, default: bool = True) -> bool:
    """Получить булевый ввод."""
    default_str = "y" if default else "n"
    while True:
        result = input(f"{prompt} (y/n) [{default_str}]: ").strip().lower()
        if not result:
            return default
        if result in ["y", "yes", "да"]:
            return True
        if result in ["n", "no", "нет"]:
            return False
        print("❌ Введите y (да) или n (нет)")


def get_float_input(
    prompt: str, default: float, min_val: float = 0.0, max_val: float = 1.0
) -> float:
    """Получить дробное число."""
    while True:
        result = input(f"{prompt} [{default}]: ").strip()
        if not result:
            return default
        try:
            value = float(result)
            if min_val <= value <= max_val:
                return value
            print(f"❌ Значение должно быть от {min_val} до {max_val}")
        except ValueError:
            print("❌ Введите число")


def select_safety_mode() -> str:
    """Выбор режима безопасности."""
    print("\nДоступные режимы безопасности:\n")
    modes = {
        "1": ("disabled", "Без LLM фильтрации (только vector rules)"),
        "2": ("external", "Внешний LLM для санитизации"),
        "3": ("local", "Локальный safety сервис"),
        "4": ("hybrid", "Гибридный (local + external fallback)"),
    }

    for key, (mode, desc) in modes.items():
        print(f"  {key}. {mode:12} - {desc}")

    print()
    current_mode = settings.SAFETY_MODE
    print(f"Текущий режим из настроек: {current_mode}")

    while True:
        choice = input(f"\nВыберите режим (1-4) или Enter для текущего [{current_mode}]: ").strip()

        if not choice:
            return current_mode

        if choice in modes:
            return modes[choice][0]

        print("❌ Неверный выбор. Введите число от 1 до 4")


def capture_filter_config(
    filter_service: ContentFilterService | None = None, mode: str = "local", **extra_params
) -> dict:
    """Сохранить конфигурацию фильтра."""
    config = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "extra_params": extra_params,
    }

    if filter_service:
        config.update(
            {
                "safety_mode": filter_service.active_mode.value,
                "requested_mode": filter_service.requested_mode.value,
                "default_threshold": filter_service.default_threshold,
                "safety_llm_enabled": filter_service.safety_llm_enabled,
            }
        )

    # Всегда сохраняем settings если в локальном режиме
    if mode == "local":
        config["settings"] = {
            "FILTER_DEFAULT_THRESHOLD": settings.FILTER_DEFAULT_THRESHOLD,
            "FILTER_FALLBACK_THRESHOLD": settings.FILTER_FALLBACK_THRESHOLD,
            "VECTOR_SEARCH_TOP_K": settings.VECTOR_SEARCH_TOP_K,
            "SAFETY_MODE": settings.SAFETY_MODE,
            "STREAM_GUARD_MODE": settings.STREAM_GUARD_MODE,
        }

    return config


def clean_text(text: str) -> str:
    """Очистка текста."""
    if pd.isna(text):
        return ""
    text = str(text).strip()
    # Удаление лишних пробелов
    text = " ".join(text.split())
    return text


async def filter_questions(
    questions: list[str],
    filter_service: ContentFilterService,
    use_llm: bool = False,
    enable_vector_rules: bool = True,
    enable_prompt_modification: bool = True,
) -> list[dict]:
    """
    Прогнать вопросы через фильтр.

    Args:
        questions: Список вопросов для фильтрации
        filter_service: Инициализированный сервис фильтрации
        use_llm: Использовать ли LLM для санитизации
        enable_vector_rules: Включить vector rules
        enable_prompt_modification: Включить модификацию промпта

    Returns:
        Список результатов фильтрации с метаданными
    """
    results = []

    print(f"\n🔍 Прогон {len(questions)} вопросов через фильтр...\n")

    for idx, question in enumerate(tqdm(questions, desc="Фильтрация")):
        try:
            # Прогнать через фильтр
            filter_result = await filter_service.check_content(
                text=question,
                use_llm=use_llm,
                use_linked_docs=True,
                is_input=True,
                enable_vector_rules=enable_vector_rules,
                enable_prompt_modification=enable_prompt_modification,
                enable_output_cleaning=False,  # Это для input, не нужно
            )

            # Извлечь метаданные
            matched_rules = len(filter_result.matches)
            rule_ids = [m.rule_id for m in filter_result.matches]
            rule_texts = [m.rule_text for m in filter_result.matches]
            categories = [m.category for m in filter_result.matches]
            risk_levels = [m.risk_level for m in filter_result.matches]
            relevance_scores = [m.relevance_score for m in filter_result.matches]

            # Максимальные значения
            max_risk = max(risk_levels) if risk_levels else 0
            max_relevance = max(relevance_scores) if relevance_scores else 0.0

            # Extract component latencies
            component_latencies = filter_result.component_latencies_ms or {}

            result_row = {
                "index": idx,
                "original_text": filter_result.original_text,
                "modified_text": filter_result.modified_text,
                "was_modified": filter_result.was_modified,
                "matched_rules_count": matched_rules,
                "max_risk_level": max_risk,
                "max_relevance_score": max_relevance,
                "rule_ids": "|".join(rule_ids) if rule_ids else "",
                "rule_texts": "|".join(rule_texts) if rule_texts else "",
                "categories": "|".join(categories) if categories else "",
                "risk_levels": "|".join(map(str, risk_levels)) if risk_levels else "",
                "relevance_scores": (
                    "|".join(f"{s:.4f}" for s in relevance_scores) if relevance_scores else ""
                ),
                "detection_latency_ms": filter_result.detection_latency_ms,
                "sanitization_latency_ms": filter_result.sanitization_latency_ms,
                "safety_mode": filter_result.safety_mode,
                "components_vector_rules": filter_result.components_applied.get(
                    "vector_rules", False
                ),
                "components_safety_llm": filter_result.components_applied.get("safety_llm", False),
                "components_prompt_mod": filter_result.components_applied.get(
                    "prompt_modification", False
                ),
                # Component-level latencies
                "latency_vector_rules_ms": component_latencies.get("vector_rules"),
                "latency_prompt_modification_ms": component_latencies.get("prompt_modification"),
                "latency_safety_llm_ms": component_latencies.get("safety_llm"),
                "latency_output_cleaning_ms": component_latencies.get("output_cleaning"),
                "processed_at": filter_result.processed_at.isoformat(),
            }

            results.append(result_row)

        except Exception as e:
            logger.error(f"Ошибка при фильтрации вопроса {idx}: {e}", exc_info=True)
            # Записать ошибку
            results.append(
                {
                    "index": idx,
                    "original_text": question,
                    "modified_text": None,
                    "was_modified": False,
                    "matched_rules_count": 0,
                    "max_risk_level": 0,
                    "max_relevance_score": 0.0,
                    "rule_ids": "",
                    "rule_texts": "",
                    "categories": "",
                    "risk_levels": "",
                    "relevance_scores": "",
                    "detection_latency_ms": None,
                    "sanitization_latency_ms": None,
                    "safety_mode": None,
                    "components_vector_rules": False,
                    "components_safety_llm": False,
                    "components_prompt_mod": False,
                    # Component-level latencies (error case)
                    "latency_vector_rules_ms": None,
                    "latency_prompt_modification_ms": None,
                    "latency_safety_llm_ms": None,
                    "latency_output_cleaning_ms": None,
                    "processed_at": datetime.now().isoformat(),
                    "error": str(e),
                }
            )

    return results


async def filter_questions_via_api(
    questions: list[str],
    api_base: str,
    api_endpoint: str = "/query",
    api_key: str | None = None,
    use_llm_filter: bool = False,
    use_linked_docs: bool = True,
    use_cache: bool = True,
    batch_size: int = 5,
) -> list[dict]:
    """
    Прогнать вопросы через API фильтра с асинхронной обработкой батчами.

    Args:
        questions: Список вопросов для фильтрации
        api_base: Base URL API (например, http://localhost:8000)
        api_endpoint: Путь к endpoint (например, /query или /filter)
        api_key: API ключ (если требуется)
        use_llm_filter: Использовать ли LLM для фильтрации
        use_linked_docs: Использовать ли связанные документы
        use_cache: Использовать ли кеширование на стороне API
        batch_size: Размер батча для параллельной обработки (по умолчанию 5)

    Returns:
        Список результатов фильтрации с метаданными (в исходном порядке)
    """
    if httpx is None:
        print("❌ Модуль httpx не установлен. Установите: pip install httpx")
        sys.exit(1)

    full_url = f"{api_base}{api_endpoint}"
    cache_status = "с кешем" if use_cache else "без кеша"
    print(
        f"\n🔍 Прогон {len(questions)} вопросов через API ({full_url}) {cache_status} батчами по {batch_size}...\n"
    )

    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key

    # Результаты с сохранением порядка (индекс -> результат)
    results_dict = {}

    async def process_question(idx: int, question: str, client: httpx.AsyncClient) -> None:
        """Обработать один вопрос и сохранить результат."""
        try:
            # Запрос к API
            response = await client.post(
                full_url,
                headers=headers,
                json={
                    "query": question,
                    "use_llm_filter": use_llm_filter,
                    "use_linked_docs": use_linked_docs,
                    "use_cache": use_cache,
                },
            )

            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", response.text[:200])
                except Exception:
                    error_detail = response.text[:200]
                raise Exception(f"API вернул код {response.status_code}: {error_detail}")

            data = response.json()

            # Извлечь INPUT filter result из ответа
            input_filter = data.get("input_filter_result", {})
            if not input_filter:
                # Возможно старая версия API
                input_filter = {}

            matches = input_filter.get("matches", [])
            matched_rules = len(matches)

            rule_ids = [m.get("rule_id", "") for m in matches]
            rule_texts = [m.get("rule_text", "") for m in matches]
            categories = [m.get("category", "") for m in matches]
            risk_levels = [m.get("risk_level", 0) for m in matches]
            relevance_scores = [m.get("relevance_score", 0.0) for m in matches]

            max_risk = max(risk_levels) if risk_levels else 0
            max_relevance = max(relevance_scores) if relevance_scores else 0.0

            # Извлечь OUTPUT filter result из ответа
            output_filter = data.get("output_filter_result", {})
            output_matches = output_filter.get("matches", [])
            output_matched_rules = len(output_matches)

            output_rule_ids = [m.get("rule_id", "") for m in output_matches]
            output_categories = [m.get("category", "") for m in output_matches]
            output_risk_levels = [m.get("risk_level", 0) for m in output_matches]

            output_max_risk = max(output_risk_levels) if output_risk_levels else 0

            # Extract component latencies for INPUT
            input_component_latencies = input_filter.get("component_latencies_ms", {})
            # Extract component latencies for OUTPUT
            output_component_latencies = output_filter.get("component_latencies_ms", {})

            result_row = {
                "index": idx,
                # INPUT filter
                "original_text": input_filter.get("original_text", question),
                "modified_text": input_filter.get("modified_text"),
                "was_modified": input_filter.get("was_modified", False),
                "matched_rules_count": matched_rules,
                "max_risk_level": max_risk,
                "max_relevance_score": max_relevance,
                "rule_ids": "|".join(rule_ids) if rule_ids else "",
                "rule_texts": "|".join(rule_texts) if rule_texts else "",
                "categories": "|".join(categories) if categories else "",
                "risk_levels": "|".join(map(str, risk_levels)) if risk_levels else "",
                "relevance_scores": (
                    "|".join(f"{s:.4f}" for s in relevance_scores) if relevance_scores else ""
                ),
                "detection_latency_ms": input_filter.get("detection_latency_ms"),
                "sanitization_latency_ms": input_filter.get("sanitization_latency_ms"),
                "safety_mode": input_filter.get("safety_mode"),
                "components_vector_rules": input_filter.get("components_applied", {}).get(
                    "vector_rules", False
                ),
                "components_safety_llm": input_filter.get("components_applied", {}).get(
                    "safety_llm", False
                ),
                "components_prompt_mod": input_filter.get("components_applied", {}).get(
                    "prompt_modification", False
                ),
                # Component-level latencies (INPUT)
                "latency_vector_rules_ms": input_component_latencies.get("vector_rules"),
                "latency_prompt_modification_ms": input_component_latencies.get(
                    "prompt_modification"
                ),
                "latency_safety_llm_ms": input_component_latencies.get("safety_llm"),
                "latency_output_cleaning_ms": input_component_latencies.get("output_cleaning"),
                # LLM response
                "llm_response": data.get("response", ""),
                # OUTPUT filter (если есть)
                "output_modified_text": output_filter.get("modified_text"),
                "output_was_modified": output_filter.get("was_modified", False),
                "output_matched_rules_count": output_matched_rules,
                "output_max_risk_level": output_max_risk,
                "output_rule_ids": "|".join(output_rule_ids) if output_rule_ids else "",
                "output_categories": "|".join(output_categories) if output_categories else "",
                # Component-level latencies (OUTPUT)
                "output_latency_vector_rules_ms": output_component_latencies.get("vector_rules"),
                "output_latency_output_cleaning_ms": output_component_latencies.get(
                    "output_cleaning"
                ),
                "output_latency_safety_llm_ms": output_component_latencies.get("safety_llm"),
                # Timing
                "processed_at": input_filter.get("processed_at", datetime.now().isoformat()),
                "api_response_time_ms": response.elapsed.total_seconds() * 1000,
            }

            # Сохранить в словарь с индексом для сохранения порядка
            results_dict[idx] = result_row

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка при API запросе для вопроса {idx}: {error_msg}", exc_info=True)
            print(f"\n⚠️  Ошибка для вопроса {idx}: {error_msg}")

            # Записать ошибку
            results_dict[idx] = {
                "index": idx,
                # INPUT filter
                "original_text": question,
                "modified_text": None,
                "was_modified": False,
                "matched_rules_count": 0,
                "max_risk_level": 0,
                "max_relevance_score": 0.0,
                "rule_ids": "",
                "rule_texts": "",
                "categories": "",
                "risk_levels": "",
                "relevance_scores": "",
                "detection_latency_ms": None,
                "sanitization_latency_ms": None,
                "safety_mode": None,
                "components_vector_rules": False,
                "components_safety_llm": False,
                "components_prompt_mod": False,
                # Component-level latencies (INPUT, error case)
                "latency_vector_rules_ms": None,
                "latency_prompt_modification_ms": None,
                "latency_safety_llm_ms": None,
                "latency_output_cleaning_ms": None,
                # LLM response
                "llm_response": None,
                # OUTPUT filter
                "output_modified_text": None,
                "output_was_modified": False,
                "output_matched_rules_count": 0,
                "output_max_risk_level": 0,
                "output_rule_ids": "",
                "output_categories": "",
                # Component-level latencies (OUTPUT, error case)
                "output_latency_vector_rules_ms": None,
                "output_latency_output_cleaning_ms": None,
                "output_latency_safety_llm_ms": None,
                # Timing
                "processed_at": datetime.now().isoformat(),
                "api_response_time_ms": None,
                "error": str(e),
            }

    # Обработка батчами
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Разбить на батчи
        total_batches = (len(questions) + batch_size - 1) // batch_size

        with tqdm(total=len(questions), desc="Фильтрация через API") as pbar:
            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(questions))

                # Создать задачи для текущего батча
                tasks = [
                    process_question(idx, questions[idx], client)
                    for idx in range(start_idx, end_idx)
                ]

                # Запустить батч параллельно
                await asyncio.gather(*tasks)

                # Обновить progress bar
                pbar.update(end_idx - start_idx)

    # Вернуть результаты в правильном порядке
    return [results_dict[idx] for idx in range(len(questions))]


def print_summary(results: list[dict]):
    """Вывести статистику результатов."""
    df = pd.DataFrame(results)

    print_header("📊 Статистика результатов")

    total = len(df)
    modified = df["was_modified"].sum()
    with_matches = (df["matched_rules_count"] > 0).sum()

    print(f"Всего вопросов:           {total}")
    print(f"Модифицировано:           {modified} ({modified/total*100:.1f}%)")
    print(f"С срабатыванием правил:   {with_matches} ({with_matches/total*100:.1f}%)")
    print()

    if with_matches > 0:
        print("Категории срабатываний:")
        # Развернуть категории
        all_categories = []
        for cats in df[df["categories"] != ""]["categories"]:
            all_categories.extend(cats.split("|"))

        if all_categories:
            from collections import Counter

            cat_counts = Counter(all_categories)
            for cat, count in cat_counts.most_common():
                print(f"  • {cat:20} - {count} раз")
        print()

    print("Уровни риска:")
    risk_dist = df[df["max_risk_level"] > 0]["max_risk_level"].value_counts().sort_index()
    for risk, count in risk_dist.items():
        print(f"  • Risk Level {int(risk)}:  {count} вопросов")
    print()

    avg_latency = df["detection_latency_ms"].mean()
    print(f"Средняя латентность детекции: {avg_latency:.2f} ms")

    if df["sanitization_latency_ms"].notna().any():
        avg_sanitization = df["sanitization_latency_ms"].mean()
        print(f"Средняя латентность санитизации: {avg_sanitization:.2f} ms")

    print()


async def main():
    """Основная функция."""
    print_header("🔍 Бенчмарк фильтра AVI")

    # 1. Запросить путь к CSV файлу
    csv_path = get_text_input("Введите путь к CSV файлу с вопросами")
    csv_file = Path(csv_path)

    if not csv_file.exists():
        print(f"❌ Файл не найден: {csv_path}")
        sys.exit(1)

    # 2. Загрузить CSV
    print(f"\n📂 Загрузка файла: {csv_file.name}")
    try:
        # Попробовать разные кодировки
        try:
            df = pd.read_csv(csv_file, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_file, encoding="cp1251")
        print(f"✅ Загружено {len(df)} строк")
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        sys.exit(1)

    # Удалить Unnamed колонки (индексы pandas)
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # 3. Показать колонки и выбрать колонку с вопросами
    print_columns(df)

    questions_col = select_column(df, "Введите номер или название колонки с вопросами: ")

    print(f"\n✅ Выбрана колонка: '{questions_col}'")

    # 4. Выбор режима работы
    print_header("🔧 Режим работы")

    print("Выберите режим работы:\n")
    print("  1. Локальный - прямой вызов ContentFilterService (быстрее)")
    print("  2. Через API - HTTP запросы к /query endpoint (для удалённого API)")
    print()

    while True:
        mode_choice = input("Введите номер режима (1-2) [1]: ").strip()
        if not mode_choice:
            mode_choice = "1"

        if mode_choice in ["1", "2"]:
            break
        print("❌ Неверный выбор. Введите 1 или 2")

    use_api_mode = mode_choice == "2"

    if use_api_mode:
        print("\n✅ Режим: Через API")

        # Настройки API
        api_base = get_text_input("\nВведите base URL API", "http://localhost:8000")
        api_base = api_base.rstrip("/")  # Убрать trailing slash

        # API endpoint path
        api_endpoint = get_text_input("Введите путь к endpoint", "/query")
        if not api_endpoint.startswith("/"):
            api_endpoint = "/" + api_endpoint

        # API ключ (опционально)
        api_key_input = get_text_input("Введите API ключ (или Enter если не нужен)", "")
        api_key = api_key_input if api_key_input else None

        if api_key:
            print("✅ API ключ установлен")
        else:
            print("ℹ️  Работа без API ключа")

        print(f"✅ API endpoint: {api_base}{api_endpoint}")

    else:
        print("\n✅ Режим: Локальный")

    # 5. Настройки фильтрации
    print_header("⚙️  Настройки фильтрации")

    if use_api_mode:
        # Для API режима - простые параметры
        use_llm_filter = get_bool_input("Использовать LLM фильтрацию?", default=True)
        use_linked_docs = get_bool_input("Использовать связанные документы?", default=True)
        use_cache = get_bool_input("Использовать кеширование на стороне API?", default=False)

        # Dummy переменные для совместимости
        safety_mode = "api"
        use_llm = use_llm_filter
        enable_vector_rules = True
        enable_prompt_mod = True
        custom_threshold = None
        filter_service = None

    else:
        # Для локального режима - полные настройки
        # Режим безопасности
        safety_mode = select_safety_mode()
        print(f"✅ Режим безопасности: {safety_mode}")

        # Использовать ли LLM для санитизации
        use_llm = False
        if safety_mode != "disabled":
            use_llm = get_bool_input("\nИспользовать LLM для санитизации текста?", default=False)

        # Дополнительные параметры
        print("\n🔧 Дополнительные параметры:\n")
        enable_vector_rules = get_bool_input("  Включить vector rules?", default=True)
        enable_prompt_mod = get_bool_input(
            "  Включить модификацию промпта при срабатывании?", default=True
        )

        # Порог (если нужно переопределить)
        override_threshold = get_bool_input("\nПереопределить порог срабатывания?", default=False)
        custom_threshold = None
        if override_threshold:
            custom_threshold = get_float_input(
                "  Порог (0.0-1.0)", settings.FILTER_DEFAULT_THRESHOLD, 0.0, 1.0
            )
            print(f"✅ Установлен порог: {custom_threshold}")

    # 6. Инициализировать фильтр (только для локального режима)
    if not use_api_mode:
        print_header("🚀 Инициализация фильтра")

        try:
            vector_db = VectorDBService()
            filter_service = ContentFilterService(
                vector_db=vector_db, mode=safety_mode, default_threshold=custom_threshold
            )
            print("✅ Фильтр инициализирован")
            print(f"   Активный режим: {filter_service.active_mode.value}")
            print(f"   Порог: {filter_service.default_threshold}")
            print(f"   LLM доступен: {filter_service.safety_llm_enabled}")
        except Exception as e:
            print(f"❌ Ошибка инициализации фильтра: {e}")
            logger.error("Ошибка инициализации", exc_info=True)
            sys.exit(1)

    # 6. Подготовить вопросы
    questions = [clean_text(q) for q in df[questions_col]]
    questions = [q for q in questions if q]  # Удалить пустые

    print(f"\n📝 Подготовлено {len(questions)} вопросов для фильтрации")

    # Подтверждение
    confirm = get_bool_input("\n🚀 Начать фильтрацию?", default=True)
    if not confirm:
        print("❌ Отменено пользователем")
        sys.exit(0)

    # 7. Прогнать через фильтр
    try:
        if use_api_mode:
            results = await filter_questions_via_api(
                questions=questions,
                api_base=api_base,
                api_endpoint=api_endpoint,
                api_key=api_key,
                use_llm_filter=use_llm_filter,
                use_linked_docs=use_linked_docs,
                use_cache=use_cache,
            )
        else:
            results = await filter_questions(
                questions=questions,
                filter_service=filter_service,
                use_llm=use_llm,
                enable_vector_rules=enable_vector_rules,
                enable_prompt_modification=enable_prompt_mod,
            )
    except Exception as e:
        print(f"\n❌ Ошибка при фильтрации: {e}")
        logger.error("Ошибка при фильтрации", exc_info=True)
        sys.exit(1)

    # 8. Сохранить результаты
    print_header("💾 Сохранение результатов")

    # Директория для сохранения
    output_dir = get_text_input("Директория для сохранения результатов", "data/benchmarks/filter")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Имя файла с timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = csv_file.stem

    # Сохранить результаты в CSV
    results_df = pd.DataFrame(results)
    results_path = output_path / f"{base_name}_filtered_{timestamp}.csv"
    results_df.to_csv(results_path, index=False, encoding="utf-8")
    print(f"✅ Результаты: {results_path}")

    # Сохранить конфигурацию
    if use_api_mode:
        config = capture_filter_config(
            mode="api",
            api_base=api_base,
            api_endpoint=api_endpoint,
            api_key_provided=bool(api_key),
            use_llm_filter=use_llm_filter,
            use_linked_docs=use_linked_docs,
            use_cache=use_cache,
            dataset_file=str(csv_file.absolute()),
            questions_column=questions_col,
            total_questions=len(questions),
        )
    else:
        config = capture_filter_config(
            filter_service=filter_service,
            mode="local",
            use_llm=use_llm,
            enable_vector_rules=enable_vector_rules,
            enable_prompt_modification=enable_prompt_mod,
            dataset_file=str(csv_file.absolute()),
            questions_column=questions_col,
            total_questions=len(questions),
        )
    config_path = output_path / f"{base_name}_config_{timestamp}.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"✅ Конфигурация: {config_path}")

    # 9. Показать статистику
    print_summary(results)

    # 10. Показать примеры
    print_header("📋 Примеры результатов")

    # Показать 3 примера с срабатыванием
    matched = results_df[results_df["matched_rules_count"] > 0]
    if len(matched) > 0:
        print("Примеры с срабатыванием правил:\n")
        for _idx, row in matched.head(3).iterrows():
            print(f"{'─' * 70}")
            print(f"Вопрос: {row['original_text'][:100]}...")
            print(f"Правила: {row['matched_rules_count']}")
            print(f"Категории: {row['categories']}")
            print(f"Max Risk: {row['max_risk_level']}")
            print(f"Max Relevance: {row['max_relevance_score']:.4f}")
            if row["was_modified"]:
                print("Модифицирован: Да")
        print()
    else:
        print("⚠️  Нет вопросов с срабатыванием правил\n")

    print_header("✨ Готово!")
    print(f"Результаты сохранены в: {output_path.absolute()}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        print(f"\n❌ Произошла ошибка: {e}")
        sys.exit(1)

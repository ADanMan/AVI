#!/usr/bin/env python3
"""Проверка готовности системы к запуску бенчмарков."""

import json
import sys
from pathlib import Path

import httpx


def check_api_running() -> bool:
    """Проверка что API запущен."""
    try:
        response = httpx.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API запущен и работает")
            return True
        else:
            print(f"❌ API вернул статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API не доступен: {e}")
        print("   Запустите: python -m uvicorn src.api.main:app --reload")
        return False


def check_datasets() -> bool:
    """Проверка наличия датасетов."""
    benchmark_dir = Path("data/benchmarks")
    if not benchmark_dir.exists():
        print("❌ Директория data/benchmarks не найдена")
        return False

    required_files = [
        "toxigen.csv",
        "prompt_injections.csv",
        "pii_masking_200k.csv",
        "poly_fever.csv",
        "shades_nationality.csv",
    ]

    missing = []
    for file in required_files:
        file_path = benchmark_dir / file
        if not file_path.exists():
            missing.append(file)
        else:
            size = file_path.stat().st_size
            lines = sum(1 for _ in open(file_path)) - 1  # Minus header
            print(f"✅ {file}: {lines} строк ({size // 1024}KB)")

    if missing:
        print(f"❌ Отсутствуют датасеты: {', '.join(missing)}")
        print("   Запустите: PYTHONPATH=/home/user/AVI python scripts/setup_data.py")
        return False

    return True


def check_config() -> bool:
    """Проверка конфигурации бенчмарков."""
    config_path = Path("config/benchmark_config.json")
    if not config_path.exists():
        print("❌ Файл config/benchmark_config.json не найден")
        return False

    try:
        with open(config_path) as f:
            config = json.load(f)

        models = config.get("models", [])
        benchmarks = config.get("benchmarks", [])

        if not models:
            print("❌ В конфигурации нет моделей")
            return False

        if not benchmarks:
            print("❌ В конфигурации нет бенчмарков")
            return False

        print(f"✅ Конфигурация: {len(models)} моделей, {len(benchmarks)} датасетов")
        return True

    except json.JSONDecodeError as e:
        print(f"❌ Ошибка в JSON конфигурации: {e}")
        return False


def check_results_dir() -> bool:
    """Проверка директории для результатов."""
    results_dir = Path("artifacts/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ Директория для результатов: {results_dir}")
    return True


def main():
    """Запуск всех проверок."""
    print("🔍 Проверка готовности системы к запуску бенчмарков...\n")

    checks = [
        ("API", check_api_running),
        ("Датасеты", check_datasets),
        ("Конфигурация", check_config),
        ("Директория результатов", check_results_dir),
    ]

    all_passed = True
    for name, check_func in checks:
        print(f"\n📋 Проверка: {name}")
        if not check_func():
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ Все проверки пройдены! Система готова к запуску бенчмарков.")
        print("\nДля запуска:")
        print("  1. Скрипт: ./scripts/run_quick_benchmark.sh")
        print("  2. Python: PYTHONPATH=/home/user/AVI python scripts/benchmark_test.py")
        sys.exit(0)
    else:
        print("❌ Некоторые проверки не пройдены. Исправьте ошибки выше.")
        sys.exit(1)


if __name__ == "__main__":
    main()

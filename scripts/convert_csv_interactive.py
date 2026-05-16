#!/usr/bin/env python3
"""
Интерактивный скрипт для преобразования CSV в форматы AVI.

Позволяет указать какие колонки использовать для:
- filter_rules (вопросы/правила фильтрации)
- vector_documents (ответы/документы)
- автоматически создает links между ними

Использование:
    python scripts/convert_csv_interactive.py
"""

import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.utils.logger import logger


def print_header(text: str):
    """Печать заголовка."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_columns(df: pd.DataFrame):
    """Показать доступные колонки."""
    print("\nДоступные колонки в файле:\n")
    for idx, col in enumerate(df.columns, 1):
        sample = df[col].iloc[0] if len(df) > 0 else "н/д"
        # Обрезаем длинные значения
        sample_str = str(sample)[:50] + "..." if len(str(sample)) > 50 else str(sample)
        print(f"  {idx}. {col:30} | Пример: {sample_str}")
    print()


def select_column(df: pd.DataFrame, prompt: str, allow_skip: bool = False) -> str | None:
    """Интерактивный выбор колонки."""
    while True:
        choice = input(prompt).strip()

        if allow_skip and choice.lower() in ["", "skip", "пропустить", "нет"]:
            return None

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


def get_int_input(prompt: str, default: int, min_val: int = 1, max_val: int = 5) -> int:
    """Получить числовой ввод."""
    while True:
        result = input(f"{prompt} [{default}]: ").strip()
        if not result:
            return default
        try:
            value = int(result)
            if min_val <= value <= max_val:
                return value
            print(f"❌ Значение должно быть от {min_val} до {max_val}")
        except ValueError:
            print("❌ Введите целое число")


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


def clean_text(text: str) -> str:
    """Очистка текста."""
    if pd.isna(text):
        return ""
    text = str(text).strip()
    # Удаление лишних пробелов
    text = " ".join(text.split())
    return text


def main():
    """Основная функция."""
    print_header("Конвертер CSV в форматы AVI")

    # 1. Запросить путь к CSV файлу
    csv_path = get_text_input("Введите путь к CSV файлу")
    csv_file = Path(csv_path)

    if not csv_file.exists():
        print(f"❌ Файл не найден: {csv_path}")
        sys.exit(1)

    # 2. Загрузить CSV
    print(f"\n📂 Загрузка файла: {csv_file.name}")
    try:
        df = pd.read_csv(csv_file, encoding="utf-8")
        print(f"✅ Загружено {len(df)} строк")
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        sys.exit(1)

    # Удалить Unnamed колонки (индексы pandas)
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # 3. Показать колонки
    print_columns(df)

    # 4. Выбрать колонку для вопросов (filter_rules)
    print_header("Настройка filter_rules (правила фильтрации)")
    print("Выберите колонку с вопросами или текстом для фильтрации.\n")

    questions_col = select_column(df, "Введите номер или название колонки для вопросов/правил: ")

    # Настройки для filter_rules
    print("\nНастройки для filter_rules:")
    rule_category = get_text_input("  Категория", "General_QA")
    risk_level = get_int_input("  Уровень риска (1-5)", 3, 1, 5)
    threshold = get_float_input("  Порог срабатывания (0.0-1.0)", 0.75, 0.0, 1.0)

    # 5. Выбрать колонку для ответов (vector_documents)
    print_header("Настройка vector_documents (документы)")
    print("Выберите колонку с ответами или документами.\n")

    answers_col = select_column(df, "Введите номер или название колонки для ответов: ")

    # Настройки для vector_documents
    print("\nНастройки для vector_documents:")
    doc_category = get_text_input("  Категория", "QA_Answers")
    doc_source = get_text_input("  Источник данных", "csv_import")

    # 6. Дополнительные колонки (опционально)
    print("\n💡 Дополнительные колонки (необязательно):")
    source_col = select_column(
        df,
        "  Колонка 'источник' (нажмите Enter чтобы пропустить): ",
        allow_skip=True,
    )
    category_col = select_column(
        df, "  Колонка 'категория' (нажмите Enter чтобы пропустить): ", allow_skip=True
    )

    # 7. Выбрать директорию для сохранения
    print_header("Сохранение результатов")
    output_dir = get_text_input("Директория для сохранения", "data/raw")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 8. Создать filter_rules
    print("\n🔧 Создание filter_rules.csv...")
    filter_rules = []
    for idx, row in df.iterrows():
        question = clean_text(row[questions_col])
        if not question:
            continue

        # Категория из колонки или дефолт
        category = (
            clean_text(row[category_col])
            if category_col and category_col in df.columns
            else rule_category
        )

        filter_rules.append(
            {
                "id": f"rule_{idx}",
                "text": question,
                "category": category,
                "risk_level": risk_level,
                "threshold": threshold,
            }
        )

    fr_df = pd.DataFrame(filter_rules)
    fr_path = output_path / "filter_rules.csv"
    fr_df.to_csv(fr_path, index=False, encoding="utf-8")
    print(f"✅ Создано {len(fr_df)} правил -> {fr_path}")

    # 9. Создать vector_documents
    print("\n📄 Создание vector_documents.csv...")
    vector_docs = []
    for idx, row in df.iterrows():
        answer = clean_text(row[answers_col])
        if not answer:
            continue

        # Источник из колонки или дефолт
        source = (
            clean_text(row[source_col]) if source_col and source_col in df.columns else doc_source
        )

        # Категория из колонки или дефолт
        category = (
            clean_text(row[category_col])
            if category_col and category_col in df.columns
            else doc_category
        )

        vector_docs.append(
            {"id": f"doc_{idx}", "text": answer, "category": category, "source": source}
        )

    vd_df = pd.DataFrame(vector_docs)
    vd_path = output_path / "vector_documents.csv"
    vd_df.to_csv(vd_path, index=False, encoding="utf-8")
    print(f"✅ Создано {len(vd_df)} документов -> {vd_path}")

    # 10. Создать links
    print("\n🔗 Создание links.csv...")
    links = []
    for idx in range(len(df)):
        # Создаем связь только если есть и вопрос и ответ
        if idx < len(filter_rules) and idx < len(vector_docs):
            links.append(
                {
                    "rule_id": f"rule_{idx}",
                    "document_id": f"doc_{idx}",
                    "is_approved": True,
                }
            )

    ln_df = pd.DataFrame(links)
    ln_path = output_path / "links.csv"
    ln_df.to_csv(ln_path, index=False, encoding="utf-8")
    print(f"✅ Создано {len(ln_df)} связей -> {ln_path}")

    # 11. Итоги
    print_header("✨ Готово!")
    print("Создано:")
    print(f"  • {len(fr_df)} правил фильтрации")
    print(f"  • {len(vd_df)} документов")
    print(f"  • {len(ln_df)} связей")
    print(f"\nФайлы сохранены в: {output_path.absolute()}\n")

    # 12. Показать примеры
    print("📋 Примеры созданных данных:\n")
    print("Filter Rules (первые 3):")
    print(fr_df.head(3).to_string(index=False))
    print("\nVector Documents (первые 3):")
    print(vd_df.head(3).to_string(index=False))
    print("\nLinks (первые 3):")
    print(ln_df.head(3).to_string(index=False))
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        print(f"\n❌ Произошла ошибка: {e}")
        sys.exit(1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile
import hashlib
import sys

def print_progress(label: str, current: int, total: int, duplicates: int = 0, sample: str = ""):
    pct = int((current / total) * 100) if total else 100
    msg = f"\r{label}: {current}/{total} ({pct}%) | Дубликаты: {duplicates}"
    if sample:
        msg += f" | Последний дубликат: {sample[:50]}"
    sys.stdout.write(msg)
    sys.stdout.flush()
    if current == total:
        print()

def remove_duplicates_verbose(input_file: str, block_size: int = 100000):
    """
    Удаляет дубликаты из очень большого файла с прогресс-баром, количеством удалённых дубликатов
    и примером последнего дубликата.
    """
    if not os.path.exists(input_file):
        print(f"Файл {input_file} не найден.")
        return

    print("Разделение файла на блоки с уникальными строками внутри блока...")

    temp_blocks = []
    current_block = []
    block_counter = 0
    total_lines = sum(1 for _ in open(input_file, 'r', encoding='utf-8'))
    processed_lines = 0
    duplicates_total = 0

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.rstrip('\n')
            current_block.append(stripped)
            processed_lines += 1
            print_progress("Обработка строк для блоков", processed_lines, total_lines, duplicates_total)

            if len(current_block) >= block_size:
                block_counter += 1
                temp_fd, temp_path = tempfile.mkstemp()
                os.close(temp_fd)
                # сохраняем уникальные строки блока
                block_unique = set(current_block)
                duplicates_total += len(current_block) - len(block_unique)
                with open(temp_path, 'w', encoding='utf-8') as bf:
                    for l in block_unique:
                        bf.write(l + '\n')
                temp_blocks.append(temp_path)
                current_block.clear()

        # последний блок
        if current_block:
            block_counter += 1
            temp_fd, temp_path = tempfile.mkstemp()
            os.close(temp_fd)
            block_unique = set(current_block)
            duplicates_total += len(current_block) - len(block_unique)
            with open(temp_path, 'w', encoding='utf-8') as bf:
                for l in block_unique:
                    bf.write(l + '\n')
            temp_blocks.append(temp_path)
            current_block.clear()

    print(f"\nВсего блоков: {len(temp_blocks)}, дубликаты внутри блоков: {duplicates_total}")

    # Объединяем блоки с прогрессом и мониторингом дубликатов между блоками
    final_fd, final_path = tempfile.mkstemp()
    os.close(final_fd)
    seen_hashes = set()
    duplicates_between_blocks = 0

    for block_idx, block_path in enumerate(temp_blocks, 1):
        with open(block_path, 'r', encoding='utf-8') as bf, open(final_path, 'a', encoding='utf-8') as final_file:
            block_lines = sum(1 for _ in open(block_path, 'r', encoding='utf-8'))
            processed_in_block = 0
            for line in bf:
                stripped = line.rstrip('\n')
                h = hashlib.sha256(stripped.encode('utf-8')).hexdigest()
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    final_file.write(stripped + '\n')
                else:
                    duplicates_between_blocks += 1
                    print_progress(f"Объединение блока {block_idx}", processed_in_block, block_lines,
                                   duplicates_between_blocks, stripped)
                processed_in_block += 1
                if processed_in_block % 1000 == 0 or processed_in_block == block_lines:
                    print_progress(f"Объединение блока {block_idx}", processed_in_block, block_lines,
                                   duplicates_between_blocks)
        os.remove(block_path)

    os.replace(final_path, input_file)
    print(f"\nВсе дубликаты удалены. Общие дубликаты: {duplicates_total + duplicates_between_blocks}")
    print(f"Файл обновлен: {input_file}")

if __name__ == "__main__":
    remove_duplicates_verbose("generations.txt")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sys
import tempfile
from bip_utils import P2PKHAddrDecoder

def ask_start():
    while True:
        ans = input("Начать фильтрацию адресов на mainnet/testnet? (Y/N): ").strip().upper()
        if ans in ("Y", "N"):
            return ans == "Y"

def is_testnet(address: str) -> bool:
    """Проверяет, является ли адрес testnet."""
    # P2PKH: mainnet '1', testnet 'm' или 'n'
    if address.startswith("m") or address.startswith("n"):
        return True
    elif address.startswith("1"):
        return False
    else:
        # Проверка через bip_utils
        try:
            decoded = P2PKHAddrDecoder.DecodeAddr(address)
            version = decoded[0]
            return version != 0x00  # mainnet P2PKH = 0x00
        except Exception:
            return False

def load_existing_addresses(file_path):
    """Возвращает множество адресов из существующего JSON-файла для продолжения."""
    addresses = set()
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                for r in data:
                    addresses.add(r["address"])
            except json.JSONDecodeError:
                pass
    return addresses

def append_record(file_path, record, first=False):
    """Добавляет запись в JSON файл потоково."""
    mode = 'w' if first else 'a'
    with open(file_path, mode, encoding='utf-8') as f:
        if first:
            f.write("[\n")
        else:
            f.write(",\n")
        json.dump(record, f, ensure_ascii=False)
        
def finalize_file(file_path):
    """Закрывает JSON массив в файле."""
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write("\n]")

def filter_addresses_stream(input_file, main_file="main_list.json", test_file="test_list.json", batch_size=1000):
    while True:
        if not ask_start():
            continue

        main_addresses = load_existing_addresses(main_file)
        test_addresses = load_existing_addresses(test_file)

        # Временные файлы для потоковой записи
        temp_main_fd, temp_main_path = tempfile.mkstemp()
        temp_test_fd, temp_test_path = tempfile.mkstemp()
        os.close(temp_main_fd)
        os.close(temp_test_fd)
        main_first = True if not os.path.exists(main_file) or os.path.getsize(main_file)==0 else False
        test_first = True if not os.path.exists(test_file) or os.path.getsize(test_file)==0 else False

        new_main = 0
        new_test = 0
        total_processed = 0

        with open(input_file, 'r', encoding='utf-8') as f_in:
            try:
                gen_data = json.load(f_in)
            except json.JSONDecodeError:
                print("Ошибка: JSON файл пустой или повреждён.")
                return

            for record in gen_data:
                addr = record.get("address")
                if not addr:
                    continue

                if addr in main_addresses or addr in test_addresses:
                    continue

                entry = {
                    "mnemonic": record.get("mnemonic"),
                    "wif": record.get("wif"),
                    "address": addr
                }

                if is_testnet(addr):
                    append_record(temp_test_path, entry, first=test_first)
                    test_first = False
                    test_addresses.add(addr)
                    new_test += 1
                else:
                    append_record(temp_main_path, entry, first=main_first)
                    main_first = False
                    main_addresses.add(addr)
                    new_main += 1

                total_processed += 1
                sys.stdout.write(f"\rОбработано: {total_processed}, новые main: {new_main}, новые test: {new_test}")
                sys.stdout.flush()

                if (new_main + new_test) > 0 and (new_main + new_test) % batch_size == 0:
                    ans = input(f"\nДобавлено {new_main} main и {new_test} test. Продолжить? (Y/N): ").strip().upper()
                    if ans != "Y":
                        print("\nОстановка фильтрации. Сохраняем прогресс.")
                        break

        # Завершаем JSON массивы
        finalize_file(temp_main_path)
        finalize_file(temp_test_path)

        # Объединяем с существующими файлами
        if os.path.exists(main_file):
            with open(main_file, 'r', encoding='utf-8') as f_old, open(temp_main_path, 'r', encoding='utf-8') as f_new:
                old_data = f_old.read().rstrip(']')
                new_data = f_new.read().lstrip('[')
                with open(main_file, 'w', encoding='utf-8') as f_out:
                    f_out.write(old_data + ',' + new_data if old_data.strip() else new_data)
        else:
            os.replace(temp_main_path, main_file)

        if os.path.exists(test_file):
            with open(test_file, 'r', encoding='utf-8') as f_old, open(temp_test_path, 'r', encoding='utf-8') as f_new:
                old_data = f_old.read().rstrip(']')
                new_data = f_new.read().lstrip('[')
                with open(test_file, 'w', encoding='utf-8') as f_out:
                    f_out.write(old_data + ',' + new_data if old_data.strip() else new_data)
        else:
            os.replace(temp_test_path, test_file)

        print(f"\nСессия завершена. Новых main: {new_main}, новых test: {new_test}\n")
        break  # одна сессия завершена

if __name__ == "__main__":
    filter_addresses_stream("gen_seed-wif.json")
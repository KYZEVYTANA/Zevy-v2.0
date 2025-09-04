add-address.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sys
import tempfile
from bip_utils import WifDecoder, P2PKHAddr

def ask_start():
    """Спрашивает пользователя о начале работы."""
    while True:
        ans = input("Начать добавление адресов к WIF-ключам? (Y/N): ").strip().upper()
        if ans in ("Y", "N"):
            return ans == "Y"

def wif_to_address(wif: str) -> str:
    """Переводим WIF в Bitcoin P2PKH адрес."""
    priv_key_bytes = WifDecoder.Decode(wif)
    addr = P2PKHAddr.EncodeKey(priv_key_bytes)
    return addr

def process_addresses_stream(input_file: str, batch_size: int = 1000):
    """Обрабатывает JSON файл потоково, минимально используя память."""
    while True:
        if not ask_start():
            continue

        temp_fd, temp_path = tempfile.mkstemp()
        os.close(temp_fd)
        new_addresses = 0
        total_processed = 0

        # Загружаем только для определения уже обработанных мнемоник
        processed_mnemonics = set()
        if os.path.exists(input_file):
            with open(input_file, 'r', encoding='utf-8') as f:
                try:
                    for item in json.load(f):
                        if "mnemonic" in item:
                            processed_mnemonics.add(item["mnemonic"])
                except json.JSONDecodeError:
                    pass

        # Потоковая обработка
        with open(input_file, 'r', encoding='utf-8') as f_in, open(temp_path, 'w', encoding='utf-8') as f_out:
            f_out.write("[\n")
            first_record = True

            try:
                for record in json.load(f_in):
                    if "mnemonic" not in record:
                        continue

                    mnemonic = record["mnemonic"]
                    if mnemonic in processed_mnemonics and "address" in record and record["address"]:
                        pass  # уже обработано
                    else:
                        wif = record.get("wif")
                        if wif:
                            try:
                                record["address"] = wif_to_address(wif)
                                new_addresses += 1
                            except Exception as e:
                                print(f"\nОшибка при генерации адреса для WIF: {wif}\n{e}")

                    # Потоковая запись в JSON
                    if not first_record:
                        f_out.write(",\n")
                    else:
                        first_record = False
                    json.dump(record, f_out, ensure_ascii=False)

                    total_processed += 1
                    sys.stdout.write(f"\rОбработано {total_processed} записей, новых адресов: {new_addresses}")
                    sys.stdout.flush()

                    if new_addresses > 0 and new_addresses % batch_size == 0:
                        ans = input(f"\n{new_addresses} новых адресов добавлено. Продолжить? (Y/N): ").strip().upper()
                        if ans != "Y":
                            print("\nОстановка. Сохраняем прогресс и возвращаемся к началу.")
                            break

            except json.JSONDecodeError:
                print("Ошибка чтения JSON файла.")
            
            f_out.write("\n]")

        # Заменяем оригинальный файл
        os.replace(temp_path, input_file)
        print(f"\nСессия завершена. Всего новых адресов добавлено: {new_addresses}\n")

if __name__ == "__main__":
    process_addresses_stream("gen_seed-wif.json")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, WifEncoder
import sys

def ask_start():
    """Спрашивает пользователя о начале работы."""
    while True:
        ans = input("Начать перевод мнемонических фраз в WIF? (Y/N): ").strip().upper()
        if ans in ("Y", "N"):
            return ans == "Y"

def mnemonic_to_wif(mnemonic: str) -> str:
    """Переводим BIP-39 мнемоническую фразу в WIF ключ."""
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    bip44_wallet = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    priv_key_bytes = bip44_wallet.PrivateKey().Raw().ToBytes()
    wif = WifEncoder.Encode(priv_key_bytes, compressed=True)
    return wif

def load_processed_mnemonics(output_file):
    """Загружает уже обработанные фразы в set для быстрого поиска."""
    processed = set()
    total_done = 0
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                for r in data:
                    processed.add(r["mnemonic"])
                total_done = len(processed)
            except json.JSONDecodeError:
                pass
    return processed, total_done

def append_to_json(output_file, record):
    """Добавляет запись в JSON файл, не загружая весь файл."""
    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        with open(output_file, 'r+', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
            data.append(record)
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
    else:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([record], f, ensure_ascii=False, indent=2)

def print_progress(total_done, new_done):
    sys.stdout.write(f"\rИтого переведено: {total_done} | Переведено в этой сессии: {new_done}")
    sys.stdout.flush()

def main():
    input_file = "generations.txt"
    output_file = "gen_seed-wif.json"

    if not os.path.exists(input_file):
        print(f"Файл {input_file} не найден.")
        return

    while True:
        if not ask_start():
            continue

        processed_mnemonics, total_done = load_processed_mnemonics(output_file)
        new_done = 0  # Количество переводов за текущую сессию

        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                mnemonic = line.strip()
                if mnemonic in processed_mnemonics:
                    continue

                try:
                    wif = mnemonic_to_wif(mnemonic)
                except Exception as e:
                    print(f"\nОшибка при обработке фразы: {mnemonic}\n{e}")
                    continue

                record = {"mnemonic": mnemonic, "wif": wif}
                append_to_json(output_file, record)
                processed_mnemonics.add(mnemonic)
                total_done += 1
                new_done += 1

                if new_done % 1000 == 0:
                    print_progress(total_done, new_done)
                    ans = input(f"\n{new_done} новых фраз переведено. Продолжить? (Y/N): ").strip().upper()
                    if ans != "Y":
                        print("\nОстановка перевода. Возврат к началу.")
                        break

                if new_done % 10 == 0:
                    print_progress(total_done, new_done)

        print(f"\nСессия завершена. Всего переведено: {total_done}.\n")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import tempfile
import time
from bip_utils import (
    WifDecoder, WifEncoder,
    P2PKHAddr,
    Bip39SeedGenerator, Bip44, Bip44Coins
)


def mnemonics_to_json_stream(txt_file: str, json_file: str, batch_size: int = 50, pause_sec: float = 0.05):
    """Читаем сид-фразы построчно, записываем JSON потоково с паузами и прогрессом."""
    if not os.path.exists(txt_file):
        print(f"Файл {txt_file} не найден.")
        return

    # если JSON существует, пропускаем уже записанные строки
    existing_count = 0
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            existing_count = sum(1 for line in f if line.strip().startswith("{"))

    total_lines = sum(1 for _ in open(txt_file, "r", encoding="utf-8"))
    processed_lines = 0
    new_records = 0

    with open(json_file, "a" if existing_count else "w", encoding="utf-8") as fout, open(txt_file, "r", encoding="utf-8") as fin:
        if not existing_count:
            fout.write("[\n")
            first = True
        else:
            # нужно убрать последнюю "]" чтобы продолжить JSON
            fout.seek(0, os.SEEK_END)
            fout.seek(fout.tell() - 2, os.SEEK_SET)  # убираем \n]
            fout.write(",\n")
            first = False

        for idx, line in enumerate(fin):
            if idx < existing_count:
                continue  # пропускаем уже обработанные строки

            mnemonic = line.strip()
            if not mnemonic:
                continue

            try:
                seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
                bip44_mst = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
                priv_key_obj = bip44_mst.PrivateKey()
                wif = WifEncoder.Encode(priv_key_obj.Raw().ToBytes())

                record = {"mnemonic": mnemonic, "wif": wif}

                if not first:
                    fout.write(",\n")
                else:
                    first = False
                json.dump(record, fout, ensure_ascii=False)
                new_records += 1

            except Exception as e:
                print(f"\nОшибка при обработке: {mnemonic}\n{e}")

            processed_lines += 1
            if processed_lines % batch_size == 0:
                percent = (processed_lines + existing_count) / total_lines * 100
                print(f"\r📄 Обработано {processed_lines + existing_count}/{total_lines} ({percent:.1f}%) сид-фраз", end="")
                time.sleep(pause_sec)

        fout.write("\n]")

    print(f"\n✅ Сид-фразы из {txt_file} записаны/добавлены в {json_file}")


def process_addresses_stream_lazy_autosave_resume(json_file: str, batch_size: int = 50, pause_sec: float = 0.05, autosave_interval: int = 100):
    """Добавляем адреса в JSON потоково с автосохранением и возобновлением."""
    if not os.path.exists(json_file):
        print(f"Файл {json_file} не найден.")
        return

    # считаем количество объектов и уже имеющих адрес
    total_records = 0
    processed_records = 0
    with open(json_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("{"):
                total_records += 1
                if '"address"' in line:
                    processed_records += 1

    if processed_records == total_records:
        print("Все записи уже обработаны. Адреса добавлены.")
        return

    temp_fd, temp_path = tempfile.mkstemp()
    os.close(temp_fd)

    new_addresses = 0
    autosave_count = 0

    with open(json_file, "r", encoding="utf-8") as fin, open(temp_path, "w", encoding="utf-8") as fout:
        fout.write("[\n")
        first = True
        buffer = ""
        in_object = False
        brace_count = 0
        current_idx = 0

        while True:
            c = fin.read(1)
            if not c:
                break

            buffer += c

            if c == "{":
                in_object = True
                brace_count += 1
            elif c == "}":
                brace_count -= 1
                if brace_count == 0 and in_object:
                    try:
                        record = json.loads(buffer)
                        current_idx += 1

                        # если адрес уже есть, просто копируем
                        if "address" not in record or not record["address"]:
                            wif = record.get("wif")
                            if wif:
                                try:
                                    record["address"] = P2PKHAddr.EncodeKey(WifDecoder.Decode(wif))
                                    new_addresses += 1
                                except Exception as e:
                                    print(f"\nОшибка при генерации адреса: {wif}\n{e}")

                        if not first:
                            fout.write(",\n")
                        else:
                            first = False
                        json.dump(record, fout, ensure_ascii=False)

                        # прогресс и пауза
                        if current_idx % batch_size == 0:
                            percent = current_idx / total_records * 100
                            print(f"\r📝 Обработано {current_idx}/{total_records} ({percent:.1f}%), новых адресов: {new_addresses}", end="")
                            time.sleep(pause_sec)

                        # автосохранение
                        autosave_count += 1
                        if autosave_count >= autosave_interval:
                            fout.flush()
                            os.fsync(fout.fileno())
                            autosave_count = 0
                            print(f"\n💾 Прогресс автоматически сохранён на {current_idx} записей")

                    except Exception as e:
                        print(f"\nОшибка при обработке JSON объекта: {e}")
                    buffer = ""
                    in_object = False

        fout.write("\n]")

    os.replace(temp_path, json_file)
    print(f"\n✅ Завершено. Добавлено {new_addresses} новых адресов.")


if __name__ == "__main__":
    # шаг 1: создаём/добавляем JSON из сидов потоково
    mnemonics_to_json_stream("generations.txt", "gen_seed-wif.json", batch_size=50, pause_sec=0.05)

    # шаг 2: добавляем адреса потоково с автосохранением и возобновлением
    process_addresses_stream_lazy_autosave_resume(
        "gen_seed-wif.json",
        batch_size=50,
        pause_sec=0.05,
        autosave_interval=100
    )

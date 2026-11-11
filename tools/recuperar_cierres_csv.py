#!/usr/bin/env python3
"""Recupera únicamente los tres pares indicados desde un CSV exportado de Hyperliquid.

No llama a Hyperliquid: requiere comprobar por separado que las seis patas están planas.
No reescribe los demás pares ni recalcula funding. Guarda copia de seguridad.
"""
import argparse
import csv
import json
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Argentina/Buenos_Aires')
SPECS = {
    ('LDO', 'ETH'): datetime(2026, 9, 23, 0, 0, tzinfo=TZ),
    ('JTO', 'SOL'): datetime(2026, 9, 24, 0, 0, tzinfo=TZ),
    ('EIGEN', 'ALT'): datetime(2026, 10, 20, 0, 0, tzinfo=TZ),
}
END_DAY = datetime(2026, 10, 23, tzinfo=TZ)


def records(csv_path):
    out = []
    with csv_path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        required = {'time', 'coin', 'dir', 'sz', 'fee', 'closedPnl'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Faltan columnas obligatorias en el CSV')
        for row in reader:
            try:
                stamp = datetime.strptime(row['time'].strip(), '%d/%m/%Y - %H:%M:%S').replace(tzinfo=TZ)
                out.append({'stamp': stamp, 'coin': row['coin'].strip(), 'dir': row['dir'].strip(),
                            'qty': Decimal(row['sz']), 'fee': Decimal(row['fee']),
                            'net': Decimal(row['closedPnl'])})
            except (ValueError, KeyError) as exc:
                raise ValueError('Fila inválida de CSV: ' + str(row)) from exc
    return out


def reconstruct(csv_path):
    fills = records(csv_path)
    reconstructed = []
    for (long, short), start in SPECS.items():
        legs = []
        for coin, open_dir, close_dir in ((long, 'Open Long', 'Close Long'),
                                          (short, 'Open Short', 'Close Short')):
            leg = sorted([r for r in fills if r['coin'] == coin and start <= r['stamp'] < END_DAY],
                         key=lambda r: r['stamp'])
            if not leg or leg[0]['dir'] != open_dir or leg[-1]['dir'] != close_dir:
                raise ValueError(f'{coin}: falta apertura/cierre esperado; no se modificará nada')
            quantity = sum((r['qty'] if r['dir'] == open_dir else -r['qty'] if r['dir'] == close_dir
                            else Decimal('NaN')) for r in leg)
            if not quantity.is_finite() or abs(quantity) > Decimal('0.0000001'):
                raise ValueError(f'{coin}: no se demuestra posición cero (saldo {quantity})')
            legs.append(leg)
        cycle = [r for leg in legs for r in leg]
        opened = min(leg[0]['stamp'] for leg in legs)
        closed = max(leg[-1]['stamp'] for leg in legs)
        # En este CSV closedPnl incluye la comisión: las aperturas muestran -fee.
        fees = sum((r['fee'] for r in cycle), Decimal(0))
        net = sum((r['net'] for r in cycle), Decimal(0))
        realized = net + fees
        item = {'id': f'{long}|{short}|{int(closed.timestamp()*1000)}',
                'long': long, 'short': short,
                'opened_at': int(opened.timestamp()*1000),
                'closed_at': int(closed.timestamp()*1000),
                'realized': float(realized), 'fees': float(fees),
                'net_realized': float(net),
                'funding': None, 'funding_complete': False, 'total_pnl': None,
                'recovery_source': 'hyperliquid-csv-aggregated',
                'recovery_note': 'Horarios del CSV con precisión de segundos (America/Argentina/Buenos_Aires); funding no disponible; requiere corroborar posiciones planas en Hyperliquid.'}
        reconstructed.append(item)
    return reconstructed


def apply(settings_path, items):
    cfg = json.loads(settings_path.read_text(encoding='utf-8'))
    if not isinstance(cfg, dict) or not isinstance(cfg.get('pairs'), list) or not isinstance(cfg.get('closed_pairs'), list):
        raise ValueError('settings.json inválido; abortado')
    for item in items:
        if not any(p.get('long') == item['long'] and p.get('short') == item['short'] for p in cfg['pairs']):
            if any(p.get('long') == item['long'] and p.get('short') == item['short'] for p in cfg['closed_pairs']):
                print('Ya archivado, se omite:', item['long'], item['short'])
                continue
            raise ValueError(f"No se encuentra activo {item['long']}/{item['short']} en este settings.json. No se modificó nada.")
    active = {(p['long'], p['short']) for p in cfg['pairs']}
    new_items = [i for i in items if (i['long'], i['short']) in active]
    if not new_items:
        return None
    cfg['pairs'] = [p for p in cfg['pairs'] if (p.get('long'), p.get('short')) not in {(i['long'], i['short']) for i in new_items}]
    cfg['closed_pairs'].extend(new_items)
    backup = settings_path.with_name(settings_path.name + '.backup_pre_recuperacion_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(settings_path, backup)
    import os, tempfile
    fd, temp = tempfile.mkstemp(dir=settings_path.parent, prefix='.settings-recuperacion-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(cfg, output, indent=2, ensure_ascii=False)
            output.flush(); os.fsync(output.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, settings_path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    return backup


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path, required=True)
    p.add_argument('--settings', type=Path, help='Ruta REAL de settings.json (solo necesaria con --aplicar)')
    p.add_argument('--aplicar', action='store_true')
    p.add_argument('--confirmo-sin-posiciones', action='store_true', help='Confirmación manual de que Hyperliquid muestra las seis patas en cero')
    args = p.parse_args()
    items = reconstruct(args.csv)
    print(json.dumps(items, ensure_ascii=False, indent=2))
    if not args.aplicar:
        print('\nVISTA PREVIA: no se modificó ningún archivo. Verificá las seis patas planas antes de aplicar.')
        return
    if not args.confirmo_sin_posiciones or not args.settings:
        p.error('Para aplicar indicá --settings y --confirmo-sin-posiciones')
    if not args.settings.is_file():
        p.error('No existe el settings.json indicado')
    backup = apply(args.settings, items)
    print('\nRECUPERACIÓN COMPLETADA. Copia de seguridad:', backup or '(sin cambios)')


if __name__ == '__main__':
    main()

from app.ocr import extract_punches, _decimal_hours_to_time

path = 'uploads/test/Screenshot_20260619_165701_Chrome.jpg'
punches = extract_punches(path, 'official')

print('Found', len(punches), 'punches:')
for p in punches:
    print(' ', p['date'], p['type'], p['time'], 'total=' + str(p['daily_total_minutes']) + 'min')

print()
print('Decimal hours conversion check:')
for val in ['4.17', '9.48', '3.83', '9.15', '4.12', '3.75', '9.43']:
    t = _decimal_hours_to_time(val)
    print(' ', val, '->', t)

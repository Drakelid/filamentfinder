import sys
import os
os.chdir('/app')
sys.path.insert(0, '/app')

from app.database import SessionLocal
from app.models import Product
import re

db = SessionLocal()
products = db.query(Product).filter(Product.active == True).limit(500).all()

missing_brand = 0
missing_color = 0
missing_weight = 0
has_all = 0
examples_missing_color = []
examples_missing_brand = []

for p in products:
    name_lower = p.name.lower()
    
    has_weight = bool(re.search(r'(\d+(?:[.,]\d+)?)\s*(kg|g)\b', name_lower))
    
    colors = ['black', 'white', 'red', 'blue', 'green', 'grey', 'gray', 'yellow', 'orange', 'pink', 'purple', 'brown', 'silver', 'gold', 'natural', 'clear', 'svart', 'hvit', 'gra', 'grå', 'rød', 'blå', 'grønn']
    has_color = any(c in name_lower for c in colors) or bool(p.color)
    
    brands = ['polymaker', 'bambu', 'esun', 'sunlu', 'creality', 'elegoo', 'flashforge', 'fiberlogy', 'spectrum', 'prusa', 'ultimaker', 'maertz', 'verbatim', 'real', 'jayo', 'eryone', 'overture', 'hatchbox', 'anycubic', 'colorfabb', 'formfutura', 'fillamentum', 'extrudr', '3djake', 'rosa3d', 'devil', 'add north', 'polyalkemi', 'kingroon', 'qidi', 'siraya', 'phrozen', 'monocure', 'liqcreate', 'inland', 'amazon', 'geeetech', 'tianse', 'ziro', 'matterhackers', 'protopasta', 'basf', 'raise3d', 'zortrax']
    has_brand = bool(p.brand) or any(b in name_lower for b in brands)
    
    if not has_brand:
        missing_brand += 1
        if len(examples_missing_brand) < 10:
            examples_missing_brand.append(p.name[:100])
    if not has_color:
        missing_color += 1
        if len(examples_missing_color) < 10:
            examples_missing_color.append(p.name[:100])
    if not has_weight:
        missing_weight += 1
    if has_brand and has_color and has_weight:
        has_all += 1

print(f'Sample of {len(products)} products:')
print(f'  Missing brand: {missing_brand}')
print(f'  Missing color: {missing_color}')  
print(f'  Missing weight: {missing_weight}')
print(f'  Has all required: {has_all}')
print()
print('Examples missing brand:')
for ex in examples_missing_brand:
    print(f'  - {ex}')
print()
print('Examples missing color:')
for ex in examples_missing_color:
    print(f'  - {ex}')

db.close()

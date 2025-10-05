#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

# Cargar la mega lista actual
with open('mega_lista_objetos_completa.json', 'r', encoding='utf-8') as f:
    mega_lista = json.load(f)

print(f"Mega lista actual: {len(mega_lista)} objetos")

# Minerales principales que necesitan variantes SCU
minerales_principales = [
    'agricium', 'quantainium', 'laranite', 'hadanite', 'titanium', 'gold', 'diamond',
    'aluminium', 'copper', 'aphorite', 'bexalite', 'borase', 'corundum', 'dolivine',
    'levskiite', 'taranite', 'zetaprolium'
]

# Añadir variantes SCU para cada mineral
objetos_añadidos = 0
for mineral in minerales_principales:
    # Verificar si ya existe el mineral base
    if mineral in mega_lista:
        # Añadir variante SCU
        key_scu = f"{mineral} (scu)"
        if key_scu not in mega_lista:
            mega_lista[key_scu] = {
                "nombre_original": f"{mineral.title()} (SCU)",
                "categoria": "Minerales y materiales"
            }
            objetos_añadidos += 1
            print(f"Añadido: {key_scu}")

# Añadir Atlasium que ya existe en el JSON
if 'atlasium (8 scu)' not in mega_lista:
    mega_lista['atlasium (scu)'] = {
        "nombre_original": "Atlasium (SCU)",
        "categoria": "Minerales y materiales"
    }
    objetos_añadidos += 1
    print(f"Añadido: atlasium (scu)")

# Guardar la mega lista actualizada
with open('mega_lista_objetos_completa.json', 'w', encoding='utf-8') as f:
    json.dump(mega_lista, f, indent=2, ensure_ascii=False)

print(f"\n✅ ACTUALIZACIÓN COMPLETA!")
print(f"Objetos añadidos: {objetos_añadidos}")
print(f"Nueva mega lista: {len(mega_lista)} objetos")

# Verificar algunos ejemplos
print(f"\nVerificando SCU añadidos:")
ejemplos = ['quantainium (scu)', 'gold (scu)', 'agricium (scu)', 'laranite (scu)']
for ejemplo in ejemplos:
    if ejemplo in mega_lista:
        print(f"✅ {ejemplo}: {mega_lista[ejemplo]['nombre_original']} ({mega_lista[ejemplo]['categoria']})")
    else:
        print(f"❌ {ejemplo}: No encontrado")

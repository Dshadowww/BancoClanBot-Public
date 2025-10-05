#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import json
from datetime import datetime

def backup_database():
    """Crea un backup completo de la base de datos"""
    try:
        # Verificar si existe la base de datos
        db_file = "/app/inventario.db"
        if not os.path.exists(db_file):
            print("⚠️ No existe inventario.db para hacer backup")
            return False
        
        # Crear directorio de backups si no existe
        backup_dir = "/app/backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Nombre del backup con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/inventario_backup_{timestamp}.db"
        
        # Copiar la base de datos
        shutil.copy2(db_file, backup_file)
        
        # Crear backup adicional de la BD principal (sin timestamp para restauración rápida)
        backup_principal = f"{backup_dir}/inventario_principal.db"
        shutil.copy2(db_file, backup_principal)
        
        # Mantener solo los últimos 10 backups (más backups para mayor seguridad)
        backups = [f for f in os.listdir(backup_dir) if f.startswith("inventario_backup_")]
        backups.sort(reverse=True)
        
        for old_backup in backups[10:]:
            os.remove(os.path.join(backup_dir, old_backup))
        
        print(f"✅ Backup completo creado: {backup_file}")
        print(f"✅ Backup principal actualizado: {backup_principal}")
        return True
        
    except Exception as e:
        print(f"❌ Error en backup: {e}")
        return False

def restore_database():
    """Restaura la base de datos desde el backup más reciente"""
    try:
        backup_dir = "/app/backups"
        if not os.path.exists(backup_dir):
            print("⚠️ No hay directorio de backups")
            return False
        
        # Primero intentar restaurar desde el backup principal
        backup_principal = os.path.join(backup_dir, "inventario_principal.db")
        if os.path.exists(backup_principal):
            shutil.copy2(backup_principal, "/app/inventario.db")
            print(f"✅ Base de datos restaurada desde backup principal: {backup_principal}")
            return True
        
        # Si no existe el principal, buscar el backup más reciente
        backups = [f for f in os.listdir(backup_dir) if f.startswith("inventario_backup_")]
        if not backups:
            print("⚠️ No hay backups disponibles")
            return False
        
        backups.sort(reverse=True)
        latest_backup = os.path.join(backup_dir, backups[0])
        
        # Restaurar la base de datos
        shutil.copy2(latest_backup, "/app/inventario.db")
        print(f"✅ Base de datos restaurada desde: {latest_backup}")
        return True
        
    except Exception as e:
        print(f"❌ Error en restauración: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Iniciando sistema de backup simple...")
    restore_database()
    backup_database()

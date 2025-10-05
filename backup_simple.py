#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import json
from datetime import datetime

def backup_database():
    """Crea un backup completo de la base de datos con múltiples copias"""
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
        
        # Crear múltiples copias de seguridad
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Backup con timestamp
        backup_file = f"{backup_dir}/inventario_backup_{timestamp}.db"
        shutil.copy2(db_file, backup_file)
        
        # Backup principal (siempre el más reciente)
        backup_principal = f"{backup_dir}/inventario_principal.db"
        shutil.copy2(db_file, backup_principal)
        
        # Backup de emergencia (cada 5 minutos)
        backup_emergency = f"{backup_dir}/inventario_emergency.db"
        shutil.copy2(db_file, backup_emergency)
        
        # Backup diario
        backup_daily = f"{backup_dir}/inventario_daily_{datetime.now().strftime('%Y%m%d')}.db"
        shutil.copy2(db_file, backup_daily)
        
        # Mantener solo los últimos 20 backups
        backups = [f for f in os.listdir(backup_dir) if f.startswith("inventario_backup_")]
        backups.sort(reverse=True)
        
        for old_backup in backups[20:]:
            os.remove(os.path.join(backup_dir, old_backup))
        
        print(f"✅ Backup completo creado: {backup_file}")
        print(f"✅ Backup principal actualizado: {backup_principal}")
        print(f"✅ Backup de emergencia actualizado: {backup_emergency}")
        print(f"✅ Backup diario actualizado: {backup_daily}")
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

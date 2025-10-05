#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import json
from datetime import datetime

def backup_to_github():
    """Crea backup de la base de datos y lo sube a GitHub"""
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
        
        # Mantener solo los últimos 3 backups
        backups = [f for f in os.listdir(backup_dir) if f.startswith("inventario_backup_")]
        backups.sort(reverse=True)
        
        for old_backup in backups[3:]:
            os.remove(os.path.join(backup_dir, old_backup))
        
        print(f"✅ Backup local creado: {backup_file}")
        
        # Subir a GitHub
        try:
            # Configurar git si no está configurado
            subprocess.run(["git", "config", "--global", "user.email", "bot@railway.app"], check=True)
            subprocess.run(["git", "config", "--global", "user.name", "Railway Bot"], check=True)
            
            # Añadir archivo al git
            subprocess.run(["git", "add", backup_file], check=True)
            
            # Commit
            commit_msg = f"Backup automático de base de datos - {timestamp}"
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            
            # Push a GitHub
            subprocess.run(["git", "push", "origin", "main"], check=True)
            
            print(f"✅ Backup subido a GitHub: {backup_file}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Error al subir a GitHub: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Error en backup: {e}")
        return False

def restore_from_github():
    """Restaura la base de datos desde el backup más reciente de GitHub"""
    try:
        backup_dir = "/app/backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Buscar el backup más reciente
        backups = [f for f in os.listdir(backup_dir) if f.startswith("inventario_backup_")]
        if not backups:
            print("⚠️ No hay backups locales disponibles")
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

def sync_with_github():
    """Sincroniza con GitHub para obtener backups más recientes"""
    try:
        # Pull de GitHub
        subprocess.run(["git", "pull", "origin", "main"], check=True)
        print("✅ Sincronizado con GitHub")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Error al sincronizar con GitHub: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Iniciando sistema de backup GitHub...")
    sync_with_github()
    restore_from_github()
    backup_to_github()

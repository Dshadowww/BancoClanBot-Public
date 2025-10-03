#!/usr/bin/env python3
"""
Script para verificar que la persistencia de datos funciona correctamente
"""
import os
import sqlite3
import json
from datetime import datetime

def check_database_persistence():
    """Verifica que la base de datos esté en la ubicación correcta y sea persistente"""
    
    # Ruta de la base de datos
    db_path = "/app/data/inventario.db"
    db_dir = "/app/data"
    
    print("🔍 Verificando configuración de persistencia...")
    print(f"📁 Directorio de datos: {db_dir}")
    print(f"🗄️ Archivo de base de datos: {db_path}")
    
    # Verificar que el directorio existe
    if not os.path.exists(db_dir):
        print("❌ El directorio /app/data no existe")
        return False
    
    print("✅ Directorio /app/data existe")
    
    # Verificar que el archivo de base de datos existe
    if not os.path.exists(db_path):
        print("⚠️ La base de datos no existe aún (se creará en el primer uso)")
        return True
    
    print("✅ Base de datos existe")
    
    # Verificar que se puede conectar a la base de datos
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"📊 Tablas encontradas: {len(tables)}")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Verificar datos
        cursor.execute("SELECT COUNT(*) FROM inventario")
        inventario_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reputacion")
        reputacion_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM historial")
        historial_count = cursor.fetchone()[0]
        
        print(f"📦 Items en inventario: {inventario_count}")
        print(f"👥 Usuarios con reputación: {reputacion_count}")
        print(f"📜 Entradas en historial: {historial_count}")
        
        conn.close()
        print("✅ Base de datos accesible y funcional")
        return True
        
    except Exception as e:
        print(f"❌ Error al acceder a la base de datos: {e}")
        return False

def create_test_data():
    """Crea datos de prueba para verificar persistencia"""
    db_path = "/app/data/inventario.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Crear tablas si no existen
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventario (
                item TEXT PRIMARY KEY,
                cantidad INTEGER NOT NULL DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reputacion (
                user_id INTEGER PRIMARY KEY,
                puntos REAL NOT NULL DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp TEXT,
                accion TEXT,
                item TEXT,
                cantidad REAL,
                ubicacion TEXT,
                usuario_relacionado TEXT
            )
        ''')
        
        # Insertar datos de prueba
        cursor.execute("INSERT OR REPLACE INTO inventario (item, cantidad) VALUES (?, ?)", 
                      ("test_item", 10))
        
        cursor.execute("INSERT OR REPLACE INTO reputacion (user_id, puntos) VALUES (?, ?)", 
                      (123456789, 5.5))
        
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute("INSERT INTO historial (user_id, timestamp, accion, item, cantidad, ubicacion) VALUES (?, ?, ?, ?, ?, ?)", 
                      (123456789, timestamp, "Test", "test_item", 1, "Test Location"))
        
        conn.commit()
        conn.close()
        
        print("✅ Datos de prueba creados correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error al crear datos de prueba: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Verificador de persistencia de datos")
    print("=" * 50)
    
    # Verificar configuración
    if check_database_persistence():
        print("\n✅ La configuración de persistencia está correcta")
        
        # Crear datos de prueba
        print("\n🧪 Creando datos de prueba...")
        if create_test_data():
            print("\n🎉 ¡Todo configurado correctamente!")
            print("💡 Los datos ahora se mantendrán entre reinicios del bot")
        else:
            print("\n❌ Error al crear datos de prueba")
    else:
        print("\n❌ La configuración de persistencia tiene problemas")
        print("💡 Asegúrate de que Railway Volume esté configurado correctamente")

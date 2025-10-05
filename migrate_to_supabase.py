#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import psycopg2
import os
from supabase_config import get_db_connection_string

def migrate_data():
    """Migra datos de SQLite a PostgreSQL (Supabase)"""
    try:
        # Conectar a SQLite
        sqlite_conn = sqlite3.connect("/app/inventario.db")
        sqlite_cursor = sqlite_conn.cursor()
        
        # Conectar a PostgreSQL
        pg_conn = psycopg2.connect(
            host="db.rdjpemonawhnuspkkeic.supabase.co",
            port=5432,
            database="postgres",
            user="postgres",
            password=os.getenv("SUPABASE_DB_PASSWORD", "")
        )
        pg_cursor = pg_conn.cursor()
        
        print("🔄 Iniciando migración de datos...")
        
        # Migrar inventario
        sqlite_cursor.execute("SELECT item, cantidad FROM inventario")
        inventario_data = sqlite_cursor.fetchall()
        
        for item, cantidad in inventario_data:
            pg_cursor.execute(
                "INSERT INTO inventario (item, cantidad) VALUES (%s, %s) ON CONFLICT (item) DO UPDATE SET cantidad = EXCLUDED.cantidad",
                (item, cantidad)
            )
        
        # Migrar registro_usuarios
        sqlite_cursor.execute("SELECT user_id, item, cantidad FROM registro_usuarios")
        usuarios_data = sqlite_cursor.fetchall()
        
        for user_id, item, cantidad in usuarios_data:
            pg_cursor.execute(
                "INSERT INTO registro_usuarios (user_id, item, cantidad) VALUES (%s, %s, %s) ON CONFLICT (user_id, item) DO UPDATE SET cantidad = EXCLUDED.cantidad",
                (user_id, item, cantidad)
            )
        
        # Migrar historial
        sqlite_cursor.execute("SELECT user_id, timestamp, accion, item, cantidad, ubicacion, usuario_relacionado FROM historial")
        historial_data = sqlite_cursor.fetchall()
        
        for user_id, timestamp, accion, item, cantidad, ubicacion, usuario_relacionado in historial_data:
            pg_cursor.execute(
                "INSERT INTO historial (user_id, timestamp, accion, item, cantidad, ubicacion, usuario_relacionado) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, timestamp, accion, item, cantidad, ubicacion, usuario_relacionado)
            )
        
        # Migrar reputacion
        sqlite_cursor.execute("SELECT user_id, puntos FROM reputacion")
        reputacion_data = sqlite_cursor.fetchall()
        
        for user_id, puntos in reputacion_data:
            pg_cursor.execute(
                "INSERT INTO reputacion (user_id, puntos) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET puntos = EXCLUDED.puntos",
                (user_id, puntos)
            )
        
        # Migrar contratos
        sqlite_cursor.execute("SELECT nombre, enlace, fecha_creacion FROM contratos")
        contratos_data = sqlite_cursor.fetchall()
        
        for nombre, enlace, fecha_creacion in contratos_data:
            pg_cursor.execute(
                "INSERT INTO contratos (nombre, enlace, fecha_creacion) VALUES (%s, %s, %s)",
                (nombre, enlace, fecha_creacion)
            )
        
        # Confirmar cambios
        pg_conn.commit()
        
        # Cerrar conexiones
        sqlite_conn.close()
        pg_conn.close()
        
        print("✅ Migración completada exitosamente!")
        return True
        
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        return False

if __name__ == "__main__":
    migrate_data()

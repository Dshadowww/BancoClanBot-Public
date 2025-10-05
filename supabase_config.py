#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from supabase import create_client, Client

# Configuración de Supabase
SUPABASE_URL = "https://rdjpemonawhnuspkkeic.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJkanBlbW9uYXdobnVzcGtrZWljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk2NDk5MjIsImV4cCI6MjA3NTIyNTkyMn0.ITm-pVwC30XqRJgafE2eoKuzmtrf-dKE1p-3dUqx_JE"

# Crear cliente de Supabase
def get_supabase_client() -> Client:
    """Obtiene el cliente de Supabase"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Configuración de base de datos PostgreSQL
DB_CONFIG = {
    'host': 'db.rdjpemonawhnuspkkeic.supabase.co',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': os.getenv('SUPABASE_DB_PASSWORD', '')  # Se configurará en Railway
}

def get_db_connection_string():
    """Obtiene la cadena de conexión a la base de datos"""
    return f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

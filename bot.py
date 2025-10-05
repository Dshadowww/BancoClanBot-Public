import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, time
import re
import sqlite3
import json
import asyncio
import psycopg
from psycopg.rows import dict_row
from supabase_config import get_supabase_client, get_db_connection_string

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="//", intents=intents)

# =========================
# CONFIGURACIÓN DE BASE DE DATOS
# =========================
# Sistema de backup automático
DB_FILE = os.getenv("DB_FILE", "/app/inventario.db")

# Configuración de Supabase
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")
USE_SUPABASE = os.getenv("USE_SUPABASE", "false").lower() == "true"

# Importar y ejecutar backup al inicio
try:
    from backup_simple import backup_database, restore_database
    print("🔄 Verificando sistema de backup...")
    # Intentar restaurar backup previo
    if restore_database():
        print("✅ Base de datos restaurada desde backup")
    else:
        print("ℹ️ No hay backup previo, creando nueva base de datos")
    # Crear nuevo backup
    backup_database()
    print("✅ Sistema de backup inicializado correctamente")
except Exception as e:
    print(f"⚠️ Error en sistema de backup: {e}")
    print("🔄 Continuando sin sistema de backup...")

DB_DIR = os.path.dirname(DB_FILE)
if DB_DIR and not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR, exist_ok=True)

def get_db_connection():
    """Obtiene conexión a la base de datos (SQLite o PostgreSQL)"""
    if USE_SUPABASE and SUPABASE_DB_PASSWORD:
        try:
            conn = psycopg.connect(
                host="db.rdjpemonawhnuspkkeic.supabase.co",
                port=5432,
                database="postgres",
                user="postgres",
                password=SUPABASE_DB_PASSWORD
            )
            return conn
        except Exception as e:
            print(f"⚠️ Error conectando a Supabase: {e}")
            print("🔄 Fallback a SQLite...")
    
    # Fallback a SQLite
    return sqlite3.connect(DB_FILE)

def init_database():
    """Inicializa la base de datos y crea las tablas si no existen"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla para el inventario global
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            item TEXT PRIMARY KEY,
            cantidad INTEGER NOT NULL DEFAULT 0
        )
    ''')
    
    # Tabla para el registro de usuarios (qué tiene cada usuario)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registro_usuarios (
            user_id INTEGER,
            item TEXT,
            cantidad INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, item)
        )
    ''')
    
    # Tabla para el historial de operaciones
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
    
    # Tabla para la reputación
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reputacion (
            user_id INTEGER PRIMARY KEY,
            puntos REAL NOT NULL DEFAULT 0
        )
    ''')
    
    # Tabla para categorías asignadas dinámicamente a items
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS item_categoria (
            item TEXT PRIMARY KEY,
            categoria TEXT NOT NULL
        )
    ''')
    
    # Tabla para contratos dinámicos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            enlace TEXT NOT NULL,
            fecha_creacion TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def get_inventario():
    """Obtiene el inventario completo desde la base de datos"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item, cantidad FROM inventario")
    inventario = dict(cursor.fetchall())
    conn.close()
    return inventario

def get_registro_usuario(user_id):
    """Obtiene el registro de un usuario específico"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item, cantidad FROM registro_usuarios WHERE user_id = ?", (user_id,))
    registro = dict(cursor.fetchall())
    conn.close()
    return registro

def get_historial_usuario(user_id):
    """Obtiene el historial de un usuario específico"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, accion, item, cantidad, ubicacion, usuario_relacionado FROM historial WHERE user_id = ? ORDER BY id", (user_id,))
    historial = cursor.fetchall()
    conn.close()
    return historial

def get_reputacion_usuario(user_id):
    """Obtiene la reputación de un usuario específico"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT puntos FROM reputacion WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_all_reputacion():
    """Obtiene toda la reputación de todos los usuarios"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, puntos FROM reputacion")
    reputacion = dict(cursor.fetchall())
    conn.close()
    return reputacion

def update_inventario(item, cantidad):
    """Actualiza la cantidad de un item en el inventario"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO inventario (item, cantidad) VALUES (?, ?)", (item, cantidad))
    conn.commit()
    conn.close()

def update_registro_usuario(user_id, item, cantidad):
    """Actualiza el registro de un usuario para un item específico"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Prevenir cantidades negativas
    cantidad_final = max(0, cantidad)
    
    # Si la cantidad es 0, eliminar el registro en lugar de guardarlo
    if cantidad_final == 0:
        cursor.execute("DELETE FROM registro_usuarios WHERE user_id = ? AND item = ?", (user_id, item))
    else:
        cursor.execute("INSERT OR REPLACE INTO registro_usuarios (user_id, item, cantidad) VALUES (?, ?, ?)", (user_id, item, cantidad_final))
    
    conn.commit()
    conn.close()

def add_historial(user_id, accion, item, cantidad, ubicacion=None, usuario_relacionado=None):
    """Añade una entrada al historial"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    cursor.execute("INSERT INTO historial (user_id, timestamp, accion, item, cantidad, ubicacion, usuario_relacionado) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                   (user_id, timestamp, accion, item, cantidad, ubicacion, usuario_relacionado))
    conn.commit()
    conn.close()
    
    # Crear backup automático después de cada operación
    try:
        from backup_simple import backup_database
        backup_database()
    except:
        pass  # No fallar si el backup falla

def update_reputacion(user_id, puntos):
    """Actualiza la reputación de un usuario"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO reputacion (user_id, puntos) VALUES (?, ?)", (user_id, puntos))
    conn.commit()
    conn.close()
    
    # Crear backup automático después de cada operación
    try:
        from backup_simple import backup_database
        backup_database()
    except:
        pass  # No fallar si el backup falla

def get_categoria(item: str):
    """Obtiene la categoría de un item desde DB; si no existe, intenta con categorias estáticas; si no, None."""
    item_norm = item.lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT categoria FROM item_categoria WHERE item = ?", (item_norm,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    # Fallback a categorias estáticas
    for cat, items in categorias.items():
        if item_norm in items:
            return cat
    return None

def set_categoria(item: str, categoria: str):
    """Guarda/actualiza la categoría de un item en DB."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO item_categoria (item, categoria) VALUES (?, ?)", (item.lower(), categoria))
    conn.commit()
    conn.close()

def get_contratos():
    """Obtiene todos los contratos almacenados"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, enlace FROM contratos ORDER BY id")
    contratos = cursor.fetchall()
    conn.close()
    return contratos

def add_contrato(nombre: str, enlace: str):
    """Añade un nuevo contrato a la base de datos"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    cursor.execute("INSERT INTO contratos (nombre, enlace, fecha_creacion) VALUES (?, ?, ?)", (nombre, enlace, fecha))
    conn.commit()
    conn.close()
    
    # Crear backup automático después de cada operación
    try:
        from backup_simple import backup_database
        backup_database()
    except:
        pass  # No fallar si el backup falla

def delete_contrato(nombre: str):
    """Elimina un contrato específico de la base de datos"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contratos WHERE nombre = ?", (nombre,))
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_rows > 0

def delete_all_contratos():
    """Elimina todos los contratos de la base de datos"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contratos")
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_rows

# =========================
# SISTEMA DE BÚSQUEDA AVANZADA
# =========================
# Cargar sistema de búsqueda de objetos
try:
    with open('mega_lista_objetos_completa.json', 'r', encoding='utf-8') as f:
        sistema_busqueda = json.load(f)
    print(f"Sistema de búsqueda cargado con {len(sistema_busqueda)} objetos")
except FileNotFoundError:
    sistema_busqueda = {}
    print("⚠️ Sistema de búsqueda no encontrado. Usando sistema básico.")

def buscar_objetos(termino_busqueda, limite=25):
    """Busca objetos que coincidan con el término de búsqueda usando búsqueda híbrida"""
    termino = termino_busqueda.lower().strip()
    if not termino:
        return []
    
    # FILTRO: Bloquear naves y partes de naves
    terminos_bloqueados = ['ship', 'nave', 'armor', 'ammunition', 'parts', 'dealer', 'rental', 'polaris', 'constellation', 'cutlass', 'freelancer', 'hornet', 'gladius', 'sabre', 'avenger', 'aurora', 'mustang', '300i', '315p', '350r', '100i', '125a', '135c', 'blade', 'glaive', 'scythe', 'hammerhead', 'starfarer', 'retaliator', 'merlin', 'm50', 'scout', 'talisman']
    if any(termino_bloqueado in termino for termino_bloqueado in terminos_bloqueados):
        return []
    
    resultados_prefijo = []
    resultados_contenido = []
    
    # BÚSQUEDA EN SISTEMA DE BÚSQUEDA (JSON)
    if sistema_busqueda:
        for nombre_normalizado, datos in sistema_busqueda.items():
            nombre_original = datos['nombre_original']
            nombre_lower = nombre_original.lower()
            
            # FILTRO: Normalizar nombres de medicinas para evitar duplicados
            nombre_normalizado_busqueda = nombre_lower
            if 'medpen' in nombre_lower and 'hemozal' in nombre_lower:
                nombre_normalizado_busqueda = 'medpen (hemozal)'
            elif nombre_lower == 'medpen':
                nombre_normalizado_busqueda = 'medpen'
            
            # BÚSQUEDA POR PREFIJO (mayor prioridad)
            if nombre_normalizado_busqueda.startswith(termino):
                resultados_prefijo.append({
                    'nombre': nombre_original,
                    'categoria': 'Medicinas' if 'medpen' in nombre_lower else datos['categoria'],
                    'tipo': 'prefijo'
                })
            # BÚSQUEDA POR CONTENIDO (menor prioridad)
            elif termino in nombre_normalizado_busqueda:
                resultados_contenido.append({
                    'nombre': nombre_original,
                    'categoria': 'Medicinas' if 'medpen' in nombre_lower else datos['categoria'],
                    'tipo': 'contenido'
                })
    
    # BÚSQUEDA EN CATEGORÍAS ESTÁTICAS
    for categoria, items in categorias.items():
        for item in items:
            item_lower = item.lower()
            
            # BÚSQUEDA POR PREFIJO (mayor prioridad)
            if item_lower.startswith(termino):
                resultados_prefijo.append({
                    'nombre': item,
                    'categoria': categoria,
                    'tipo': 'prefijo'
                })
            # BÚSQUEDA POR CONTENIDO (menor prioridad)
            elif termino in item_lower:
                resultados_contenido.append({
                    'nombre': item,
                    'categoria': categoria,
                    'tipo': 'contenido'
                })
    
    # Combinar resultados: prefijos primero, luego contenido
    resultados = resultados_prefijo + resultados_contenido
    
    # Eliminar duplicados basándose en el nombre normalizado
    resultados_unicos = []
    nombres_vistos = set()
    for resultado in resultados:
        # Normalizar nombre para comparación (minúsculas y sin espacios extra)
        nombre_normalizado = resultado['nombre'].lower().strip()
        if nombre_normalizado not in nombres_vistos:
            resultados_unicos.append(resultado)
            nombres_vistos.add(nombre_normalizado)
    
    # Ordenar por relevancia adicional (coincidencias exactas primero)
    resultados_unicos.sort(key=lambda x: (
        x['tipo'] == 'prefijo',  # Prefijos primero
        x['nombre'].lower() == termino,  # Coincidencias exactas
        x['nombre'].lower().startswith(termino),  # Prefijos
        len(x['nombre'])  # Nombres más cortos primero
    ), reverse=True)
    
    return resultados_unicos[:limite]

def buscar_objetos_inventario(termino_busqueda, user_id, limite=25):
    """Busca objetos que coincidan con el término de búsqueda y que estén en el inventario del usuario usando búsqueda híbrida"""
    if not sistema_busqueda:
        return []
    
    termino = termino_busqueda.lower().strip()
    if not termino:
        return []
    
    # FILTRO: Bloquear naves y partes de naves
    terminos_bloqueados = ['ship', 'nave', 'armor', 'ammunition', 'parts', 'dealer', 'rental', 'polaris', 'constellation', 'cutlass', 'freelancer', 'hornet', 'gladius', 'sabre', 'avenger', 'aurora', 'mustang', '300i', '315p', '350r', '100i', '125a', '135c', 'blade', 'glaive', 'scythe', 'hammerhead', 'starfarer', 'retaliator', 'merlin', 'm50', 'scout', 'talisman']
    if any(termino_bloqueado in termino for termino_bloqueado in terminos_bloqueados):
        return []
    
    # Obtener objetos del usuario desde la base de datos
    inventario_usuario = get_registro_usuario(user_id)
    objetos_disponibles = [nombre for nombre, cantidad in inventario_usuario.items() if cantidad > 0]
    
    resultados_prefijo = []
    resultados_contenido = []
    
    for nombre_normalizado, datos in sistema_busqueda.items():
        nombre_original = datos['nombre_original']
        nombre_lower = nombre_original.lower()
        
        # FILTRO: Normalizar nombres de medicinas para evitar duplicados
        nombre_normalizado_busqueda = nombre_lower
        if 'medpen' in nombre_lower and 'hemozal' in nombre_lower:
            nombre_normalizado_busqueda = 'medpen (hemozal)'
        elif nombre_lower == 'medpen':
            nombre_normalizado_busqueda = 'medpen'
        
        # Verificar si el usuario tiene este objeto
        if nombre_original in objetos_disponibles:
            cantidad_usuario = inventario_usuario[nombre_original]
            
            # BÚSQUEDA POR PREFIJO (mayor prioridad)
            if nombre_normalizado_busqueda.startswith(termino):
                resultados_prefijo.append({
                    'nombre': nombre_original,
                    'categoria': 'Medicinas' if 'medpen' in nombre_lower else datos['categoria'],
                    'cantidad': cantidad_usuario,
                    'tipo': 'prefijo'
                })
            # BÚSQUEDA POR CONTENIDO (menor prioridad)
            elif termino in nombre_normalizado_busqueda:
                resultados_contenido.append({
                    'nombre': nombre_original,
                    'categoria': 'Medicinas' if 'medpen' in nombre_lower else datos['categoria'],
                    'cantidad': cantidad_usuario,
                    'tipo': 'contenido'
                })
    
    # Combinar resultados: prefijos primero, luego contenido
    resultados = resultados_prefijo + resultados_contenido
    
    # Eliminar duplicados basándose en el nombre normalizado
    resultados_unicos = []
    nombres_vistos = set()
    for resultado in resultados:
        # Normalizar nombre para comparación (minúsculas y sin espacios extra)
        nombre_normalizado = resultado['nombre'].lower().strip()
        if nombre_normalizado not in nombres_vistos:
            resultados_unicos.append(resultado)
            nombres_vistos.add(nombre_normalizado)
    
    # Ordenar por relevancia adicional (coincidencias exactas primero)
    resultados_unicos.sort(key=lambda x: (
        x['tipo'] == 'prefijo',  # Prefijos primero
        x['nombre'].lower() == termino,  # Coincidencias exactas
        x['nombre'].lower().startswith(termino),  # Prefijos
        len(x['nombre'])  # Nombres más cortos primero
    ), reverse=True)
    
    return resultados_unicos[:limite]

def obtener_categoria_objeto(nombre_objeto):
    """Obtiene la categoría de un objeto usando el sistema de búsqueda"""
    nombre_normalizado = nombre_objeto.lower().strip()
    
    # Buscar coincidencia exacta primero
    if nombre_normalizado in sistema_busqueda:
        return sistema_busqueda[nombre_normalizado]['categoria']
    
    # Buscar coincidencia parcial
    for nombre_sistema, datos in sistema_busqueda.items():
        if nombre_objeto.lower() in nombre_sistema or nombre_sistema in nombre_objeto.lower():
            return datos['categoria']
    
    return None

# =========================
# DATOS ESTÁTICOS
# =========================
iconos = {
    "pepinos": "🥒", "scu iron": "⛓️", "agricium": "🪨", "agricium (raw)": "🪨", "agricium (scu)": "📦",
    "aluminium": "🪨", "aluminium (raw)": "🪨", "aluminium (scu)": "📦", "aphorite": "🪨", "aphorite (raw)": "🪨", "aphorite (scu)": "📦",
    "bexalite": "🪨", "bexalite (raw)": "🪨", "bexalite (scu)": "📦", "borase": "🪨", "borase (raw)": "🪨", "borase (scu)": "📦",
    "copper": "🪨", "copper (raw)": "🪨", "copper (scu)": "📦", "corundum": "🪨", "corundum (raw)": "🪨", "corundum (scu)": "📦",
    "diamond": "💎", "diamond (raw)": "💎", "diamond (scu)": "📦", "dolivine": "🪨", "dolivine (raw)": "🪨", "dolivine (scu)": "📦",
    "gold": "🟡", "gold (raw)": "🟡", "gold (scu)": "📦", "hadanite": "🪨", "hadanite (raw)": "🪨", "hadanite (scu)": "📦",
    "laranite": "🟣", "laranite (raw)": "🟣", "laranite (scu)": "📦", "levskiite": "🪨", "levskiite (raw)": "🪨", "levskiite (scu)": "📦",
    "quantainium": "⚠️", "quantainium (raw)": "⚠️", "quantainium (scu)": "📦", "taranite": "🪨", "taranite (raw)": "🪨", "taranite (scu)": "📦",
    "titanium": "🪨", "titanium (raw)": "🪨", "titanium (scu)": "📦", "zetaprolium": "🪨", "zetaprolium (raw)": "🪨", "zetaprolium (scu)": "📦",
    "medical supplies": "🏥",
    "p8": "🔫", "p4-ar": "🔫", "p5-ar": "🔫", "p6-ar": "🔫", "p7-ar": "🔫", "p8-ar": "🔫",
    "arclight": "🔫", "lh86": "🔫", "s-38": "🔫", "br-2": "🔫", "devastator": "🔫",
    "f55": "🔫", "fs-9": "🔫", "demeco": "🔫", "scourge": "🔫", "salvo frag": "🔫",
    "armaduras corvus": "🛡️", "armadura ligera": "🛡️", "armadura media": "🛡️",
    "armadura pesada": "🛡️", "armadura radiación": "☢️", "armadura calor": "🔥", "armadura frío": "❄️",
    "alimentos": "🍽️", "agua": "🥤", "medpen": "💊", "medpen (hemozal)": "💊", "medical supplies": "🏥"
}

categorias = {
    "Consumibles": ["alimentos", "agua", "pepinos"],
    "Minerales y materiales": ["scu iron","agricium","agricium (raw)","agricium (scu)","aluminium","aluminium (raw)","aluminium (scu)","aphorite","aphorite (raw)","aphorite (scu)","bexalite","bexalite (raw)","bexalite (scu)","borase","borase (raw)","borase (scu)","copper","copper (raw)","copper (scu)","corundum","corundum (raw)","corundum (scu)","diamond","diamond (raw)","diamond (scu)","dolivine","dolivine (raw)","dolivine (scu)","gold","gold (raw)","gold (scu)","hadanite","hadanite (raw)","hadanite (scu)","laranite","laranite (raw)","laranite (scu)","levskiite","levskiite (raw)","levskiite (scu)","quantainium","quantainium (raw)","quantainium (scu)","taranite","taranite (raw)","taranite (scu)","titanium","titanium (raw)","titanium (scu)","zetaprolium","zetaprolium (raw)","zetaprolium (scu)","medical supplies"],
    "Armas": ["p4-ar","p5-ar","p6-ar","p7-ar","p8-ar","p8","arclight","lh86","s-38","br-2","devastator","f55","fs-9","demeco","scourge","salvo frag"],
    "Armaduras": ["armaduras corvus","armadura ligera","armadura media","armadura pesada","armadura radiación","armadura calor","armadura frío"],
    "Medicinas": ["medpen", "medpen (hemozal)", "medical supplies"],
    "Otros": []
}

limites = {
    "default": 200,
    "Minerales y materiales": 5000
}

# =========================
# FUNCIONES AUXILIARES
# =========================
def normalizar(nombre):
    return nombre.lower()

def calcular_reputacion(cat, cantidad):
    if cat=="Armas": return round(0.05*cantidad, 2)
    if cat=="Armaduras": return round(0.2*cantidad, 2)
    if cat=="Consumibles": return round(0.01*cantidad, 2)
    if cat=="Medicinas": return round(0.02*cantidad, 2)
    if cat=="Minerales y materiales": return round(0.05*(cantidad/10), 2)
    return round(0.01*cantidad, 2)

def obtener_limite(item):
    categoria = get_categoria(item)
    if categoria is None:
        return limites["default"]
    return limites.get(categoria, limites["default"])

def get_limite_por_categoria(categoria):
    """Obtiene el límite para una categoría específica"""
    return limites.get(categoria, limites["default"])

# Validaciones numéricas estrictas
def es_entero_positivo(texto: str) -> bool:
    return bool(texto.isdigit()) and int(texto) > 0

def es_decimal_positivo(texto: str) -> bool:
    return bool(re.fullmatch(r"\d+(\.\d+)?", texto)) and float(texto) > 0

def barra_progreso(total: int, limite: int, ancho: int = 8) -> str:
    if limite <= 0:
        return "[{}]".format("░"*ancho)
    ratio = max(0.0, min(1.0, total/limite))
    # Cuartiles: 0, 25, 50, 75, 100 -> 0,2,4,6,8 bloques
    if ratio == 0:
        bloques = 0
    elif ratio <= 0.25:
        bloques = 2
    elif ratio <= 0.50:
        bloques = 4
    elif ratio <= 0.75:
        bloques = 6
    else:
        bloques = 8
    return "[{}{}]".format("█"*bloques, "░"*(ancho-bloques))

# =========================
# FUNCIONES DE LIMPIEZA AUTOMÁTICA
# =========================
async def limpiar_canal_diario():
    """Limpia todo el canal a las 12:00 del mediodía"""
    try:
        # Obtener el canal desde la variable de entorno o usar un canal por defecto
        canal_id = os.getenv("CANAL_CONTRATOS_ID")
        if not canal_id:
            print("⚠️ CANAL_CONTRATOS_ID no configurado. No se puede limpiar el canal.")
            return
        
        canal = bot.get_channel(int(canal_id))
        if not canal:
            print(f"❌ No se pudo encontrar el canal con ID: {canal_id}")
            return
        
        # Limpiar todos los mensajes del canal
        deleted = await canal.purge(limit=None)
        print(f"🧹 Canal limpiado: {len(deleted)} mensajes eliminados")
        
    except Exception as e:
        print(f"❌ Error al limpiar el canal: {e}")

async def anunciar_contratos_diario():
    """Anuncia todos los contratos disponibles a las 12:01"""
    try:
        # Obtener el canal desde la variable de entorno
        canal_id = os.getenv("CANAL_CONTRATOS_ID")
        if not canal_id:
            print("⚠️ CANAL_CONTRATOS_ID no configurado. No se puede anunciar contratos.")
            return
        
        canal = bot.get_channel(int(canal_id))
        if not canal:
            print(f"❌ No se pudo encontrar el canal con ID: {canal_id}")
            return
        
        # Obtener todos los contratos de la base de datos
        contratos = get_contratos()
        
        if not contratos:
            mensaje = "@here\n🔄 ** ACTUALIZACIÓN DIARIA DE LOS CONTRATOS DISPONIBLES:** 🔄\n\n**📋 CONTRATOS DISPONIBLES:**\n\n❌ **No hay contratos disponibles en este momento.**\n\n---\n💼 **Total de contratos activos: 0**\n⏰ **Actualizado automáticamente a las 12:01**"
        else:
            mensaje = "@here\n🔄 ** ACTUALIZACIÓN DIARIA DE LOS CONTRATOS DISPONIBLES:** 🔄\n\n**📋 CONTRATOS DISPONIBLES:**\n\n"
            
            for i, (nombre, enlace) in enumerate(contratos, 1):
                mensaje += f"**{i}.** **{nombre}**\n{enlace}\n\n"
            
            mensaje += f"---\n💼 **Total de contratos activos: {len(contratos)}**\n⏰ **Actualizado automáticamente a las 12:01**"
        
        # Enviar mensaje con botonera pública
        view = BotoneraView()
        await canal.send(mensaje, view=view)
        print(f"📢 Anuncio diario enviado: {len(contratos)} contratos")
        
    except Exception as e:
        print(f"❌ Error al anunciar contratos: {e}")

@tasks.loop(time=time(11, 30))
async def tarea_limpieza_diaria():
    """Tarea programada para limpiar el canal a las 12:30 España (11:30 UTC)"""
    await limpiar_canal_diario()

@tasks.loop(time=time(11, 31))
async def tarea_anuncio_diario():
    """Tarea programada para anunciar contratos a las 12:31 España (11:31 UTC)"""
    await anunciar_contratos_diario()

# =========================
# EVENTO BOT READY
# =========================
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user} (id: {bot.user.id})")
    # Inicializar la base de datos al arrancar
    init_database()
    print("Base de datos inicializada correctamente")
    
    # Iniciar las tareas programadas
    if not tarea_limpieza_diaria.is_running():
        tarea_limpieza_diaria.start()
        print("🕐 Tarea de limpieza diaria iniciada (12:00)")
    
    if not tarea_anuncio_diario.is_running():
        tarea_anuncio_diario.start()
        print("🕐 Tarea de anuncio diario iniciada (12:01)")

# =========================
# MODALES PARA INPUTS PRIVADOS
# =========================
class CantidadModal(discord.ui.Modal, title="Cantidad"):
    def __init__(self, tipo="añadir"):
        super().__init__()
        self.tipo = tipo
        self.cantidad_input = discord.ui.TextInput(
            label=f"Cantidad a {tipo}",
            placeholder="Ej: 10",
            required=True,
            max_length=10
        )
        self.add_item(self.cantidad_input)

    async def on_submit(self, interaction: discord.Interaction):
        cantidad_texto = self.cantidad_input.value.strip()
        if not es_entero_positivo(cantidad_texto):
            await interaction.response.send_message("❌ Cantidad inválida. Usa solo números enteros positivos.", ephemeral=True)
            return
        self.cantidad = int(cantidad_texto)
        await interaction.response.defer(ephemeral=True)

class NombreModal(discord.ui.Modal, title="Nombre del objeto"):
    def __init__(self):
        super().__init__()
        self.nombre_input = discord.ui.TextInput(
            label="Nombre del objeto",
            placeholder="Ej: p8, scu iron, alimentos...",
            required=True,
            max_length=50
        )
        self.add_item(self.nombre_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.nombre = normalizar(self.nombre_input.value.strip())
        await interaction.response.defer(ephemeral=True)

class UbicacionModal(discord.ui.Modal, title="Ubicación"):
    def __init__(self):
        super().__init__()
        self.ubicacion_input = discord.ui.TextInput(
            label="¿En qué ubicación se guardará?",
            placeholder="Ej: Terra, New Babbage, Port Olisar...",
            required=True,
            max_length=100
        )
        self.add_item(self.ubicacion_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.ubicacion = self.ubicacion_input.value.strip()
        await interaction.response.defer(ephemeral=True)

class TransferCantidadModal(discord.ui.Modal, title="Cantidad a transferir"):
    def __init__(self, max_cantidad=0):
        super().__init__()
        self.max_cantidad = max_cantidad
        self.cantidad_input = discord.ui.TextInput(
            label=f"Cantidad a transferir (máx {max_cantidad})",
            placeholder="Ej: 10",
            required=True,
            max_length=10
        )
        self.add_item(self.cantidad_input)

    async def on_submit(self, interaction: discord.Interaction):
        cantidad_texto = self.cantidad_input.value.strip()
        if not es_entero_positivo(cantidad_texto):
            await interaction.response.send_message("❌ Cantidad inválida. Usa solo números enteros positivos.", ephemeral=True)
            return
        self.cantidad = int(cantidad_texto)
        await interaction.response.defer(ephemeral=True)

class TransferNombreModal(discord.ui.Modal, title="Nombre del objeto"):
    def __init__(self):
        super().__init__()
        self.nombre_input = discord.ui.TextInput(
            label="Nombre del objeto a transferir",
            placeholder="Ej: p8, scu iron, alimentos...",
            required=True,
            max_length=50
        )
        self.add_item(self.nombre_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.nombre = normalizar(self.nombre_input.value.strip())
        await interaction.response.defer(ephemeral=True)

class ReputacionCantidadModal(discord.ui.Modal, title="Cantidad de reputación"):
    def __init__(self):
        super().__init__()
        self.cantidad_input = discord.ui.TextInput(
            label="Cantidad de reputación a transferir",
            placeholder="Ej: 10.5",
            required=True,
            max_length=15
        )
        self.add_item(self.cantidad_input)

    async def on_submit(self, interaction: discord.Interaction):
        cantidad_texto = self.cantidad_input.value.strip()
        if not es_decimal_positivo(cantidad_texto):
            await interaction.response.send_message("❌ Cantidad inválida. Usa solo números positivos (ej. 10 o 10.5).", ephemeral=True)
            return
        self.cantidad = float(cantidad_texto)
        await interaction.response.defer(ephemeral=True)

# =========================
# MODAL DE BÚSQUEDA DE OBJETOS
# =========================
class BusquedaObjetoModal(discord.ui.Modal, title="Buscar Objeto"):
    def __init__(self, tipo="añadir"):
        super().__init__()
        self.tipo = tipo
        self.cantidad_input = discord.ui.TextInput(
            label=f"Cantidad a {tipo}",
            placeholder="Ej: 10",
            required=True,
            max_length=10
        )
        self.busqueda_input = discord.ui.TextInput(
            label="Buscar objeto",
            placeholder="Escribe para buscar (ej: p8, arclight, agricium...)",
            required=True,
            max_length=50
        )
        self.add_item(self.cantidad_input)
        self.add_item(self.busqueda_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Validar cantidad
        cantidad_texto = self.cantidad_input.value.strip()
        if not es_entero_positivo(cantidad_texto):
            await interaction.response.send_message("❌ Cantidad inválida. Usa solo números enteros positivos.", ephemeral=True)
            return
        cantidad = int(cantidad_texto)
        
        # Buscar objetos
        termino_busqueda = self.busqueda_input.value.strip()
        if self.tipo == "retirar":
            resultados = buscar_objetos_inventario(termino_busqueda, interaction.user.id, 25)
        else:
            resultados = buscar_objetos(termino_busqueda, 25)
        
        if not resultados:
            await interaction.response.send_message(f"❌ No se encontraron objetos que coincidan con '{termino_busqueda}'. Verifica el nombre o intenta con un término más general.", ephemeral=True)
            return
        
        # Siempre mostrar selección para que el usuario confirme
        await self.mostrar_seleccion(interaction, resultados, cantidad)
    
    async def mostrar_seleccion(self, interaction, resultados, cantidad):
        # Obtener el término de búsqueda del input
        termino_busqueda = self.busqueda_input.value.strip()
        
        class SeleccionObjetoView(discord.ui.View):
            def __init__(self, resultados, cantidad, tipo):
                super().__init__(timeout=60)
                self.resultados = resultados
                self.cantidad = cantidad
                self.tipo = tipo
                self.used = False
                
                # Crear botones para cada resultado (máximo 25)
                for i, resultado in enumerate(resultados[:25]):
                    label = resultado['nombre'][:80]  # Limitar longitud
                    if len(resultado['nombre']) > 80:
                        label += "..."
                    
                    button = discord.ui.Button(
                        label=f"{i+1}. {label}",
                        style=discord.ButtonStyle.secondary,
                        custom_id=f"select_{i}"
                    )
                    
                    # Crear callback específico para este botón con closure correcto
                    def make_callback(obj):
                        async def button_callback(interaction):
                            await self.seleccionar_objeto(interaction, obj)
                        return button_callback
                    
                    button.callback = make_callback(resultado)
                    self.add_item(button)
            
            async def seleccionar_objeto(self, interaction, objeto):
                if self.used:
                    await interaction.response.send_message("Esta selección ya fue usada. Inicia de nuevo el proceso.", ephemeral=True)
                    return
                self.used = True
                
                # Eliminar el mensaje de resultados inmediatamente
                try:
                    await interaction.message.delete()
                except Exception:
                    pass
                
                # Responder a la interacción para evitar timeout
                await interaction.response.defer(ephemeral=True)
                
                await self.procesar_objeto(interaction, objeto, self.cantidad)
            
            async def procesar_objeto(self, interaction, objeto, cantidad):
                if self.tipo == "añadir":
                    await self.procesar_añadir(interaction, objeto, cantidad)
                else:
                    await self.procesar_retirar(interaction, objeto, cantidad)
            
            async def procesar_añadir(self, interaction, objeto, cantidad):
                nombre = objeto['nombre']
                categoria = objeto['categoria']
                
                # Verificar si el objeto ya existe en categorías
                categoria_existente = get_categoria(nombre)
                
                # Si no existe, usar la categoría del sistema de búsqueda
                if not categoria_existente:
                    # Mapear categorías del sistema de búsqueda a categorías del bot
                    mapeo_categorias = {
                        'ARMAS': 'Armas',
                        'MUNICION': 'Armas',  # La munición va con las armas
                        'CONSUMIBLES': 'Consumibles',
                        'MINERALES': 'Minerales y materiales',
                        'ROPA': 'Otros',
                        'ARMADURAS': 'Armaduras',
                        'OTROS': 'Otros'
                    }
                    
                    categoria_bot = mapeo_categorias.get(categoria, 'Otros')
                    set_categoria(nombre, categoria_bot)
                    categoria_existente = categoria_bot
                
                # Procesar añadir
                limite = obtener_limite(nombre)
                inventario_actual = get_inventario()
                cantidad_actual = inventario_actual.get(nombre, 0)
                cantidad_posible = min(cantidad, limite - cantidad_actual)
                
                if cantidad_posible <= 0:
                    await interaction.followup.send(f"❌ El almacén para {nombre} está lleno. No se ha añadido nada.", ephemeral=True)
                    return
                
                # Actualizar en base de datos
                update_inventario(nombre, cantidad_actual + cantidad_posible)
                
                # Actualizar registro de usuario
                registro_usuario = get_registro_usuario(interaction.user.id)
                cantidad_usuario_actual = registro_usuario.get(nombre, 0)
                update_registro_usuario(interaction.user.id, nombre, cantidad_usuario_actual + cantidad_posible)
                
                # Registrar en historial
                add_historial(interaction.user.id, "Añadido", nombre, cantidad_posible)
                
                # Calcular y actualizar reputación
                ganado = calcular_reputacion(categoria_existente, cantidad_posible)
                reputacion_actual = get_reputacion_usuario(interaction.user.id)
                update_reputacion(interaction.user.id, reputacion_actual + ganado)
                add_historial(interaction.user.id, "Ganó Reputación", "Reputación", ganado)
                
                mensaje_respuesta = f"✅ {interaction.user.mention} añadió {cantidad_posible} de {nombre} ({categoria_existente}).\nGanaste **{ganado:.2f}** :ReputacionCorvus:. Total: **{reputacion_actual + ganado:.2f}**"
                if cantidad_posible < cantidad:
                    mensaje_respuesta += f"\n⚠️ Solo se pudieron añadir {cantidad_posible} debido al límite de almacenamiento."
                
                await interaction.followup.send(mensaje_respuesta, ephemeral=True)
                # Mostrar botonera después de completar la acción
                view = BotoneraView()
                await interaction.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
            
            async def procesar_retirar(self, interaction, objeto, cantidad):
                nombre = objeto['nombre']
                
                # Verificar disponibilidad desde la base de datos
                registro_usuario = get_registro_usuario(interaction.user.id)
                inventario_actual = get_inventario()
                
                if nombre not in inventario_actual or registro_usuario.get(nombre, 0) < cantidad:
                    await interaction.followup.send("❌ No tienes suficiente cantidad o el objeto no existe.", ephemeral=True)
                    return
                
                # Actualizar inventario global
                cantidad_actual_inventario = inventario_actual.get(nombre, 0)
                update_inventario(nombre, cantidad_actual_inventario - cantidad)
                
                # Actualizar registro de usuario
                cantidad_usuario_actual = registro_usuario.get(nombre, 0)
                update_registro_usuario(interaction.user.id, nombre, cantidad_usuario_actual - cantidad)
                
                # Registrar en historial
                add_historial(interaction.user.id, "Retirado", nombre, -cantidad)
                
                await interaction.followup.send(f"✅ Retiraste {cantidad} de {nombre}.", ephemeral=True)
                # Mostrar botonera después de completar la acción
                view = BotoneraView()
                await interaction.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
        
        view = SeleccionObjetoView(resultados, cantidad, self.tipo)
        
        # Crear mensaje con los resultados
        mensaje = f"🔍 **Resultados para '{termino_busqueda}'** ({len(resultados)} encontrados):\n\n"
        for i, resultado in enumerate(resultados[:25], 1):
            if self.tipo == "retirar" and 'cantidad' in resultado:
                mensaje += f"**{i}.** {resultado['nombre']} ({resultado['categoria']}) - Disponible: {resultado['cantidad']}\n"
            else:
                mensaje += f"**{i}.** {resultado['nombre']} ({resultado['categoria']})\n"
        
        if len(resultados) > 25:
            mensaje += f"\n... y {len(resultados) - 25} más. Usa un término más específico."
        
        mensaje += f"\n\nSelecciona el objeto que quieres {self.tipo}:"
        
        await interaction.response.send_message(mensaje, view=view, ephemeral=True)
    
    async def procesar_objeto(self, interaction, objeto, cantidad):
        if self.tipo == "añadir":
            await self.procesar_añadir(interaction, objeto, cantidad)
        else:
            await self.procesar_retirar(interaction, objeto, cantidad)
    
    async def procesar_añadir(self, interaction, objeto, cantidad):
        nombre = objeto['nombre']
        categoria = objeto['categoria']
        
        # Verificar si el objeto ya existe en categorías
        categoria_existente = get_categoria(nombre)
        
        # Si no existe, usar la categoría del sistema de búsqueda
        if not categoria_existente:
            # Mapear categorías del sistema de búsqueda a categorías del bot
            mapeo_categorias = {
                'ARMAS': 'Armas',
                'MUNICION': 'Armas',  # La munición va con las armas
                'CONSUMIBLES': 'Consumibles',
                'MINERALES': 'Minerales y materiales',
                'ROPA': 'Otros',
                'ARMADURAS': 'Armaduras',
                'OTROS': 'Otros'
            }
            
            categoria_bot = mapeo_categorias.get(categoria, 'Otros')
            set_categoria(nombre, categoria_bot)
            categoria_existente = categoria_bot
        
        # Procesar añadir
        limite = obtener_limite(nombre)
        inventario_actual = get_inventario()
        cantidad_actual = inventario_actual.get(nombre, 0)
        cantidad_posible = min(cantidad, limite - cantidad_actual)
        
        if cantidad_posible <= 0:
            await interaction.response.send_message(f"❌ El almacén para {nombre} está lleno. No se ha añadido nada.", ephemeral=True)
            return
        
        # Actualizar en base de datos
        update_inventario(nombre, cantidad_actual + cantidad_posible)
        
        # Actualizar registro de usuario
        registro_usuario = get_registro_usuario(interaction.user.id)
        cantidad_usuario_actual = registro_usuario.get(nombre, 0)
        update_registro_usuario(interaction.user.id, nombre, cantidad_usuario_actual + cantidad_posible)
        
        # Registrar en historial
        add_historial(interaction.user.id, "Añadido", nombre, cantidad_posible)
        
        # Calcular y actualizar reputación
        ganado = calcular_reputacion(categoria_existente, cantidad_posible)
        reputacion_actual = get_reputacion_usuario(interaction.user.id)
        update_reputacion(interaction.user.id, reputacion_actual + ganado)
        add_historial(interaction.user.id, "Ganó Reputación", "Reputación", ganado)
        
        mensaje_respuesta = f"✅ {interaction.user.mention} añadió {cantidad_posible} de {nombre} ({categoria_existente}).\nGanaste **{ganado:.2f}** :ReputacionCorvus:. Total: **{reputacion_actual + ganado:.2f}**"
        if cantidad_posible < cantidad:
            mensaje_respuesta += f"\n⚠️ Solo se pudieron añadir {cantidad_posible} debido al límite de almacenamiento."
        
        await interaction.response.send_message(mensaje_respuesta, ephemeral=True)
        # Mostrar botonera después de completar la acción
        view = BotoneraView()
        await interaction.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
    
    async def procesar_retirar(self, interaction, objeto, cantidad):
        nombre = objeto['nombre']
        
        # Verificar disponibilidad desde la base de datos
        registro_usuario = get_registro_usuario(interaction.user.id)
        inventario_actual = get_inventario()
        
        if nombre not in inventario_actual or registro_usuario.get(nombre, 0) < cantidad:
            await interaction.response.send_message("❌ No tienes suficiente cantidad o el objeto no existe.", ephemeral=True)
            return
        
        # Actualizar inventario global
        cantidad_actual_inventario = inventario_actual.get(nombre, 0)
        update_inventario(nombre, cantidad_actual_inventario - cantidad)
        
        # Actualizar registro de usuario
        cantidad_usuario_actual = registro_usuario.get(nombre, 0)
        update_registro_usuario(interaction.user.id, nombre, cantidad_usuario_actual - cantidad)
        
        # Registrar en historial
        add_historial(interaction.user.id, "Retirado", nombre, -cantidad)
        
        await interaction.response.send_message(f"✅ Retiraste {cantidad} de {nombre}.", ephemeral=True)
        # Mostrar botonera después de completar la acción
        view = BotoneraView()
        await interaction.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)

# =========================
# BOTONERA PRINCIPAL
# =========================
class BotoneraView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def volver_menu(self, interaction):
        view = BotoneraView()
        await interaction.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)

    # -----------------
    # AÑADIR OBJETO
    # -----------------
    @discord.ui.button(label="Añadir", style=discord.ButtonStyle.green, row=0)
    async def añadir_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Usar el nuevo sistema de búsqueda
        modal = BusquedaObjetoModal(tipo="añadir")
        await interaction.response.send_modal(modal)

    # -----------------
    # RETIRAR
    # -----------------
    @discord.ui.button(label="Retirar", style=discord.ButtonStyle.red, row=0)
    async def retirar_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Usar el nuevo sistema de búsqueda
        modal = BusquedaObjetoModal(tipo="retirar")
        await interaction.response.send_modal(modal)

    # -----------------
    # HISTORIAL
    # -----------------
    @discord.ui.button(label="Historial", style=discord.ButtonStyle.gray)
    async def historial_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        historial_usuario = get_historial_usuario(interaction.user.id)
        if not historial_usuario:
            await interaction.response.send_message("No tienes historial.", ephemeral=True)
        else:
            mensaje="**📜 Historial de tus operaciones**\n\n"
            
            # Separar operaciones por tipo
            añadidos = []
            retirados = []
            transferidos = []
            reputacion_ganada = []
            
            for ts, accion, item, cant, ubic, usuario_rel in historial_usuario:
                ubic_txt = f" (Ubicación: {ubic})" if ubic else ""
                usuario_txt = f" → {usuario_rel}" if usuario_rel and accion in ["Transferido", "Recibido"] else f" ← {usuario_rel}" if usuario_rel else ""
                
                if accion == "Añadido":
                    añadidos.append(f"[{ts}] ✅ {item} ({cant}){ubic_txt}")
                elif accion == "Retirado":
                    retirados.append(f"[{ts}] ❌ {item} ({abs(cant)}){ubic_txt}")
                elif accion == "Transferido":
                    transferidos.append(f"[{ts}] 🔄 Enviado: {item} ({abs(cant)}){ubic_txt}{usuario_txt}")
                elif accion == "Recibido":
                    transferidos.append(f"[{ts}] 🔄 Recibido: {item} ({abs(cant)}){ubic_txt}{usuario_txt}")
                elif accion == "Ganó Reputación":
                    reputacion_ganada.append(f"[{ts}] 💰 +{cant:.2f} :ReputacionCorvus:")
            
            # Construir mensaje organizado
            if añadidos:
                mensaje += "**📦 Almacenes:**\n"
                for linea in añadidos:
                    mensaje += f"{linea}\n"
                mensaje += "\n"
            
            if retirados:
                mensaje += "**📤 Retirados:**\n"
                for linea in retirados:
                    mensaje += f"{linea}\n"
                mensaje += "\n"
            
            if transferidos:
                mensaje += "**🔄 Transferencias:**\n"
                for linea in transferidos:
                    mensaje += f"{linea}\n"
                mensaje += "\n"
            
            if reputacion_ganada:
                mensaje += "**💰 Reputación Ganada:**\n"
                for linea in reputacion_ganada:
                    mensaje += f"{linea}\n"
            
            await interaction.response.send_message(mensaje, ephemeral=True)
        await self.volver_menu(interaction)

    # -----------------
    # TRANSFERIR (DESHABILITADO)
    # -----------------
    # @discord.ui.button(label="Transferir", style=discord.ButtonStyle.blurple)
    # async def transferir_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     class TransferirTipoView(discord.ui.View):
    #         def __init__(self):
    #             super().__init__(timeout=60)
    #
    #         @discord.ui.button(label="Reputación", style=discord.ButtonStyle.green)
    #         async def reputacion_btn(self, interaction2: discord.Interaction, button2: discord.ui.Button):
    #             # Modal combinado para reputación
    #             class ReputacionTransferModal(discord.ui.Modal, title="Transferir Reputación"):
    #                     def __init__(self):
    #                         super().__init__()
    #                         self.cantidad_input = discord.ui.TextInput(
    #                             label="Cantidad de reputación a transferir",
    #                             placeholder="Ej: 10.5",
    #                             required=True,
    #                             max_length=15
    #                         )
    #                         self.add_item(self.cantidad_input)

    #                     async def on_submit(self, interaction: discord.Interaction):
    #                         cantidad_texto = self.cantidad_input.value.strip()
    #                         if not es_decimal_positivo(cantidad_texto):
    #                             await interaction.response.send_message("❌ Cantidad inválida. Usa solo números positivos (ej. 10 o 10.5).", ephemeral=True)
    #                             return
    #                         cantidad = float(cantidad_texto)
                        
    #                         reputacion_actual = get_reputacion_usuario(interaction.user.id)
    #                         if reputacion_actual < cantidad:
    #                             await interaction.response.send_message("❌ No tienes suficiente reputación.", ephemeral=True)
    #                             return
                        
    #                         await interaction.response.defer(ephemeral=True)
                        
    #                         class RecipientSelect(discord.ui.UserSelect):
    #                             def __init__(self):
    #                                 super().__init__(placeholder="Elige destinatario", min_values=1, max_values=1)
    #                             async def callback(self, i: discord.Interaction):
    #                                 usuario = self.values[0]
                                
                                # Actualizar reputación del remitente
    #                                 update_reputacion(interaction.user.id, reputacion_actual - cantidad)
                                
                                # Actualizar reputación del destinatario
    #                                 reputacion_destinatario = get_reputacion_usuario(usuario.id)
    #                                 update_reputacion(usuario.id, reputacion_destinatario + cantidad)
                                
                                # Registrar en historial con destinatario
    #                                 add_historial(interaction.user.id, "Transferido", f"Reputación → {usuario.name}", -cantidad, usuario_relacionado=usuario.name)
    #                                 add_historial(usuario.id, "Recibido", f"Reputación ← {interaction.user.name}", cantidad, usuario_relacionado=interaction.user.name)
                                
    #                                 await i.response.send_message(f"✅ Transferidos {cantidad:.2f} :ReputacionCorvus: a {usuario.mention}", ephemeral=True)
    #                                 await BotoneraView().volver_menu(interaction)
                        
    #                         class RecipientSelectView(discord.ui.View):
    #                             def __init__(self):
    #                                 super().__init__(timeout=60)
    #                                 self.add_item(RecipientSelect())
                        
    #                         await interaction.followup.send("Selecciona el destinatario:", view=RecipientSelectView(), ephemeral=True)
                
    #                 modal = ReputacionTransferModal()
    #                 await interaction2.response.send_modal(modal)

    #             @discord.ui.button(label="Material", style=discord.ButtonStyle.blurple)
    #             async def material_btn(self, interaction2: discord.Interaction, button2: discord.ui.Button):
                # Modal con sistema de búsqueda inteligente para transferencia de material
    #                 class MaterialTransferModal(discord.ui.Modal, title="Transferir Material"):
    #                     def __init__(self):
    #                         super().__init__()
    #                         self.cantidad_input = discord.ui.TextInput(
    #                             label="Cantidad a transferir",
    #                             placeholder="Ej: 10",
    #                             required=True,
    #                             max_length=10
    #                         )
    #                         self.busqueda_input = discord.ui.TextInput(
    #                             label="Buscar objeto a transferir",
    #                             placeholder="Escribe para buscar (ej: p4, scu iron...)",
    #                             required=True,
    #                             max_length=50
    #                         )
    #                         self.add_item(self.cantidad_input)
    #                         self.add_item(self.busqueda_input)

    #                     async def on_submit(self, interaction: discord.Interaction):
                        # Validar cantidad
    #                         cantidad_texto = self.cantidad_input.value.strip()
    #                         if not es_entero_positivo(cantidad_texto):
    #                             await interaction.response.send_message("❌ Cantidad inválida. Usa solo números enteros positivos.", ephemeral=True)
    #                             return
    #                         cantidad = int(cantidad_texto)
                        
                        # Buscar objetos en el inventario del usuario
    #                         termino_busqueda = self.busqueda_input.value.strip()
    #                         resultados = buscar_objetos_inventario(termino_busqueda, interaction.user.id, 25)
                        
    #                         if not resultados:
    #                             await interaction.response.send_message(f"❌ No se encontraron objetos que coincidan con '{termino_busqueda}' en tu inventario. Verifica el nombre o intenta con un término más general.", ephemeral=True)
    #                             return
                        
                        # Si hay muchos resultados, mostrar selección
    #                         if len(resultados) > 1:
    #                             await self.mostrar_seleccion(interaction, resultados, cantidad)
    #                         else:
    #                             objeto_seleccionado = resultados[0]
    #                             await self.procesar_transferencia(interaction, objeto_seleccionado, cantidad)
                    
    #                     async def mostrar_seleccion(self, interaction, resultados, cantidad):
    #                         termino_busqueda = self.busqueda_input.value.strip()  # Obtener el término de búsqueda
                        
    #                         class SeleccionTransferView(discord.ui.View):
    #                             def __init__(self, resultados, cantidad):
    #                                 super().__init__(timeout=60)
    #                                 self.resultados = resultados
    #                                 self.cantidad = cantidad
    #                                 self.used = False
                                
                                # Crear botones para cada resultado
    #                                 for i, resultado in enumerate(resultados[:25]):
    #                                     label = resultado['nombre'][:80]
    #                                     if len(resultado['nombre']) > 80:
    #                                         label += "..."
                                    
    #                                     button = discord.ui.Button(
    #                                         label=f"{i+1}. {label}",
    #                                         style=discord.ButtonStyle.secondary,
    #                                         custom_id=f"select_{i}"
    #                                     )
                                    
                                    # Crear callback específico para este botón
    #                                     async def button_callback(interaction, obj=resultado):
    #                                         await self.seleccionar_objeto(interaction, obj)
                                    
    #                                     button.callback = button_callback
    #                                     self.add_item(button)
                            
    #                             async def seleccionar_objeto(self, interaction, objeto):
    #                                 if self.used:
    #                                     await interaction.response.send_message("Esta selección ya fue usada. Inicia de nuevo el proceso.", ephemeral=True)
    #                                     return
    #                                 self.used = True
                                
    #                                 try:
    #                                     await interaction.message.delete()
    #                                 except Exception:
    #                                     pass
                                
    #                                 await interaction.response.defer(ephemeral=True)
    #                                 await self.procesar_transferencia(interaction, objeto, self.cantidad)
                            
    #                             async def procesar_transferencia(self, interaction, objeto, cantidad):
    #                                 nombre = objeto['nombre']
                                
    #                                 if nombre not in get_registro_usuario(interaction.user.id) or get_registro_usuario(interaction.user.id)[nombre] < cantidad:
    #                                     await interaction.followup.send("❌ No tienes suficiente cantidad o el objeto no existe.", ephemeral=True)
    #                                     return
                                
    #                                 class RecipientSelect(discord.ui.UserSelect):
    #                                     def __init__(self):
    #                                         super().__init__(placeholder="Elige destinatario", min_values=1, max_values=1)
                                    
    #                                     async def callback(self, i: discord.Interaction):
    #                                         usuario = self.values[0]
                                        
                                        # Verificar que el remitente tiene suficiente cantidad
    #                                         registro_usuario = get_registro_usuario(interaction.user.id)
    #                                         cantidad_actual_remitente = registro_usuario.get(nombre, 0)
                                        
    #                                         if cantidad_actual_remitente < cantidad:
    #                                             await i.response.send_message(f"❌ No tienes suficiente cantidad de {nombre}. Disponible: {cantidad_actual_remitente}", ephemeral=True)
    #                                             return
                                        
                                        # Actualizar registro del remitente
    #                                         update_registro_usuario(interaction.user.id, nombre, cantidad_actual_remitente - cantidad)
                                        
                                        # Actualizar registro del destinatario
    #                                         registro_destinatario = get_registro_usuario(usuario.id)
    #                                         cantidad_actual_destinatario = registro_destinatario.get(nombre, 0)
    #                                         update_registro_usuario(usuario.id, nombre, cantidad_actual_destinatario + cantidad)
                                        
                                        # Registrar en historial con destinatario
    #                                         add_historial(interaction.user.id, "Transferido", f"{nombre} → {usuario.name}", -cantidad, usuario_relacionado=usuario.name)
    #                                         add_historial(usuario.id, "Recibido", f"{nombre} ← {interaction.user.name}", cantidad, usuario_relacionado=interaction.user.name)
                                        
    #                                         await i.response.send_message(f"✅ Transferidos {cantidad} de {nombre} a {usuario.mention}", ephemeral=True)
    #                                         view = BotoneraView()
    #                                         await i.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
                                
    #                                 class RecipientSelectView(discord.ui.View):
    #                                     def __init__(self):
    #                                         super().__init__(timeout=60)
    #                                         self.add_item(RecipientSelect())
                                
    #                                 await interaction.followup.send("Selecciona el destinatario:", view=RecipientSelectView(), ephemeral=True)
                        
    #                         view = SeleccionTransferView(resultados, cantidad)
                        
                        # Crear mensaje con los resultados
    #                         mensaje = f"🔍 **Resultados para '{termino_busqueda}'** ({len(resultados)} encontrados):\n\n"
    #                         for i, resultado in enumerate(resultados[:25], 1):
    #                             mensaje += f"**{i}.** {resultado['nombre']} ({resultado['categoria']}) - Disponible: {resultado['cantidad']}\n"
                        
    #                         if len(resultados) > 25:
    #                             mensaje += f"\n... y {len(resultados) - 25} más. Usa un término más específico."
                        
    #                         mensaje += f"\n\nSelecciona el objeto que quieres transferir:"
                        
    #                         await interaction.response.send_message(mensaje, view=view, ephemeral=True)
                    
    #                     async def procesar_transferencia(self, interaction, objeto, cantidad):
    #                         nombre = objeto['nombre']
                        
    #                         if nombre not in get_registro_usuario(interaction.user.id) or get_registro_usuario(interaction.user.id)[nombre] < cantidad:
    #                             await interaction.response.send_message("❌ No tienes suficiente cantidad o el objeto no existe.", ephemeral=True)
    #                             return
                        
    #                         class RecipientSelect(discord.ui.UserSelect):
    #                             def __init__(self):
    #                                 super().__init__(placeholder="Elige destinatario", min_values=1, max_values=1)
                            
    #                             async def callback(self, i: discord.Interaction):
    #                                 usuario = self.values[0]
                                
                                # Verificar que el remitente tiene suficiente cantidad
    #                                 registro_usuario = get_registro_usuario(interaction.user.id)
    #                                 cantidad_actual_remitente = registro_usuario.get(nombre, 0)
                                
    #                                 if cantidad_actual_remitente < cantidad:
    #                                     await i.response.send_message(f"❌ No tienes suficiente cantidad de {nombre}. Disponible: {cantidad_actual_remitente}", ephemeral=True)
    #                                     return
                                
                                # Actualizar registro del remitente
    #                                 update_registro_usuario(interaction.user.id, nombre, cantidad_actual_remitente - cantidad)
                                
                                # Actualizar registro del destinatario
    #                                 registro_destinatario = get_registro_usuario(usuario.id)
    #                                 cantidad_actual_destinatario = registro_destinatario.get(nombre, 0)
    #                                 update_registro_usuario(usuario.id, nombre, cantidad_actual_destinatario + cantidad)
                                
                                # Registrar en historial con destinatario
    #                                 add_historial(interaction.user.id, "Transferido", f"{nombre} → {usuario.name}", -cantidad, usuario_relacionado=usuario.name)
    #                                 add_historial(usuario.id, "Recibido", f"{nombre} ← {interaction.user.name}", cantidad, usuario_relacionado=interaction.user.name)
                                
    #                                 await i.response.send_message(f"✅ Transferidos {cantidad} de {nombre} a {usuario.mention}", ephemeral=True)
    #                                 view = BotoneraView()
    #                                 await i.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
                        
    #                         class RecipientSelectView(discord.ui.View):
    #                             def __init__(self):
    #                                 super().__init__(timeout=60)
    #                                 self.add_item(RecipientSelect())
                        
    #                         await interaction.response.send_message("Selecciona el destinatario:", view=RecipientSelectView(), ephemeral=True)
                
    #                 modal = MaterialTransferModal()
    #                 await interaction2.response.send_modal(modal)

    #     view = TransferirTipoView()
    #     await interaction.response.send_message("Selecciona qué quieres transferir:", view=view, ephemeral=True)

    # -----------------
    # INVENTARIO
    # -----------------
    @discord.ui.button(label="Inventario", style=discord.ButtonStyle.primary)
    async def inventario_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        inventario_actual = get_inventario()
        if not inventario_actual:
            await interaction.response.send_message("📦 Inventario vacío.", ephemeral=True)
            await self.volver_menu(interaction)
            return
        # Construir un mapa categoria -> [items]
        categoria_a_items_mapa = {"Consumibles": [], "Minerales y materiales": [], "Armas": [], "Armaduras": [], "Medicinas": [], "Otros": []}
        for item, cant in inventario_actual.items():
            if cant <= 0:
                continue
            cat = get_categoria(item) or "Otros"
            categoria_a_items_mapa.setdefault(cat, [])
            categoria_a_items_mapa[cat].append(item)

        mensaje = "**📦 Banco del clan — Inventario**\n\n"
        orden_categorias = ["Consumibles", "Minerales y materiales", "Armas", "Armaduras", "Medicinas", "Otros"]
        emoji_cat_map = {"Consumibles":"🍽️","Minerales y materiales":"🪨","Armas":"🔫","Armaduras":"🛡️","Medicinas":"💊","Otros":"📦"}
        for cat in orden_categorias:
            items = categoria_a_items_mapa.get(cat, [])
            if not items:
                continue
            mensaje += f"**__{emoji_cat_map.get(cat,'📦')} {cat}__**\n"
            for item in items:
                icono = iconos.get(item, "📦")
                limite_item = obtener_limite(item)
                detalles = []
                # Obtener todos los usuarios que tienen este item
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, cantidad FROM registro_usuarios WHERE item = ? AND cantidad > 0", (item,))
                usuarios_item = cursor.fetchall()
                conn.close()
                for uid, cant in usuarios_item:
                    user = await bot.fetch_user(uid)
                    detalles.append(f"{user.name} {cant}")
                barra = barra_progreso(inventario_actual[item], limite_item)
                reparto = ", ".join(detalles)
                if reparto:
                    mensaje += f"{icono} {item} — {inventario_actual[item]}/{limite_item} {barra} | {reparto}\n"
                else:
                    mensaje += f"{icono} {item} — {inventario_actual[item]}/{limite_item} {barra}\n"
        await interaction.response.send_message(mensaje, ephemeral=True)
        await self.volver_menu(interaction)

    # -----------------
    # RANKING
    # -----------------
    @discord.ui.button(label="Ranking", style=discord.ButtonStyle.secondary)
    async def ranking_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        reputacion_todos = get_all_reputacion()
        top = sorted(reputacion_todos.items(), key=lambda x: x[1], reverse=True)
        mensaje = "**🏆 Ranking de reputación**\n"
        for i, (uid, puntos) in enumerate(top[:10],1):
            user = await bot.fetch_user(uid)
            mensaje+=f"{i}. {user.name} — {puntos:.2f} :ReputacionCorvus:\n"
        await interaction.response.send_message(mensaje, ephemeral=True)
        await self.volver_menu(interaction)

    # -----------------
    # SALDO
    # -----------------
    @discord.ui.button(label="Saldo", style=discord.ButtonStyle.primary)
    async def saldo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        puntos = get_reputacion_usuario(interaction.user.id)
        await interaction.response.send_message(f"💰 {interaction.user.mention}, tu reputación actual es: **{puntos:.2f}** :ReputacionCorvus:", ephemeral=True)
        await self.volver_menu(interaction)

    # -----------------
    # TIENDA
    # -----------------
    @discord.ui.button(label="Tienda", style=discord.ButtonStyle.success)
    async def tienda_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        mensaje = "**🛒 Tienda del clan**\n\n🚀 **Próximamente**\n\nLa tienda de naves y armaduras estará disponible pronto. Podrás comprar naves con tu reputación del clan y se te añadirá a tu cuenta del juego tu Nave o Armadura para SIEMPRE."
        await interaction.response.send_message(mensaje, ephemeral=True)
        await self.volver_menu(interaction)

    # -----------------
    # CONTRATOS
    # -----------------
    @discord.ui.button(label="Contratos", style=discord.ButtonStyle.secondary, row=1)
    async def contratos_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        contratos = get_contratos()
        if not contratos:
            mensaje = "**📋 Contratos disponibles:**\n\n❌ No hay contratos disponibles en este momento."
        else:
            mensaje = "**📋 Contratos disponibles:**\n\n"
            for i, (nombre, enlace) in enumerate(contratos, 1):
                mensaje += f"**{i}.** **{nombre}**\n{enlace}\n\n"
        await interaction.response.send_message(mensaje, ephemeral=True)
        await self.volver_menu(interaction)

# =========================
# COMANDO PARA MOSTRAR BOTONERA
# =========================
@bot.command(name="menu")
async def menu(ctx):
    view = BotoneraView()
    await ctx.send("Selecciona una opción del menú:", view=view)

# =========================
# COMANDO PARA AÑADIR CONTRATOS
# =========================
@bot.command(name="contratos")
async def contratos(ctx, *, args):
    """
    Comando para añadir contratos: //contratos (nombre del contrato) (enlace)
    Ejemplo: //contratos Armadura Corvus https://contratos.corvusnocta.org/contrato/5d4ef1a9c5064185
    """
    try:
        # Dividir el mensaje en nombre y enlace
        partes = args.strip().split()
        if len(partes) < 2:
            await ctx.send("❌ **Formato incorrecto.**\n\n**Uso:** `//contratos (nombre del contrato) (enlace)`\n**Ejemplo:** `//contratos Armadura Corvus https://contratos.corvusnocta.org/contrato/5d4ef1a9c5064185`")
            return
        
        # El último elemento es el enlace, el resto es el nombre
        enlace = partes[-1]
        nombre = " ".join(partes[:-1])
        
        # Validar que el enlace sea válido
        if not enlace.startswith(('http://', 'https://')):
            await ctx.send("❌ **Enlace inválido.** Debe empezar con `http://` o `https://`")
            return
        
        # Añadir el contrato a la base de datos
        add_contrato(nombre, enlace)
        
        # Crear mensaje de anuncio con emojis
        mensaje_anuncio = f"** ATENCIÓN SE HAN PUBLICADO NUEVOS EVENTOS Y CONTRATOS:**\n\n**{nombre.upper()}**\n{enlace}"
        
        # Enviar el mensaje de anuncio al canal
        await ctx.send(mensaje_anuncio)
        
        # Confirmar al usuario que se añadió correctamente
        await ctx.send(f"✅ **Contrato añadido exitosamente:**\n**{nombre}**\n{enlace}", ephemeral=True)
        
    except Exception as e:
        await ctx.send(f"❌ **Error al procesar el contrato:** {str(e)}", ephemeral=True)

@bot.command(name="borrar_contrato")
async def borrar_contrato(ctx, *, nombre):
    """
    Comando para borrar un contrato específico: //borrar_contrato (nombre del contrato)
    Ejemplo: //borrar_contrato test3
    """
    try:
        # Intentar eliminar el contrato
        eliminado = delete_contrato(nombre)
        
        if eliminado:
            await ctx.send(f"✅ **Contrato eliminado exitosamente:**\n**{nombre}**", ephemeral=True)
        else:
            await ctx.send(f"❌ **No se encontró el contrato:** {nombre}", ephemeral=True)
        
    except Exception as e:
        await ctx.send(f"❌ **Error al eliminar el contrato:** {str(e)}", ephemeral=True)

@bot.command(name="borrar_todos_contratos")
async def borrar_todos_contratos(ctx):
    """
    Comando para borrar todos los contratos: //borrar_todos_contratos
    """
    try:
        # Eliminar todos los contratos
        eliminados = delete_all_contratos()
        
        if eliminados > 0:
            await ctx.send(f"✅ **Se eliminaron {eliminados} contratos exitosamente.**", ephemeral=True)
        else:
            await ctx.send("❌ **No había contratos para eliminar.**", ephemeral=True)
        
    except Exception as e:
        await ctx.send(f"❌ **Error al eliminar los contratos:** {str(e)}", ephemeral=True)

@bot.command(name="anuncio")
async def anuncio_contratos(ctx):
    """Anuncia todos los contratos disponibles en el canal de contratos"""
    try:
        canal_id = os.getenv("CANAL_CONTRATOS_ID")
        if not canal_id:
            await ctx.send("❌ Canal de contratos no configurado.")
            return
        
        canal = bot.get_channel(int(canal_id))
        if not canal:
            await ctx.send(f"❌ No se pudo encontrar el canal con ID: {canal_id}")
            return
        
        contratos = get_contratos()
        
        if not contratos:
            mensaje = "🔄 ** ACTUALIZACIÓN DE LOS CONTRATOS DISPONIBLES:** 🔄\n\n**📋 CONTRATOS DISPONIBLES:**\n\n❌ **No hay contratos disponibles en este momento.**\n\n---\n💼 **Total de contratos activos: 0**\n⏰ **Actualizado manualmente**"
        else:
            mensaje = "🔄 ** ACTUALIZACIÓN DE LOS CONTRATOS DISPONIBLES:** 🔄\n\n**📋 CONTRATOS DISPONIBLES:**\n\n"
            
            for i, (nombre, enlace) in enumerate(contratos, 1):
                mensaje += f"**{i}.** **{nombre}**\n{enlace}\n\n"
            
            mensaje += f"---\n💼 **Total de contratos activos: {len(contratos)}**\n⏰ **Actualizado manualmente**"
        
        # Enviar mensaje con botonera pública
        view = BotoneraView()
        await canal.send(mensaje, view=view)
        await ctx.send(f"✅ Anuncio enviado al canal {canal.mention}")
        
    except Exception as e:
        await ctx.send(f"❌ Error al enviar anuncio: {e}")

@bot.command(name="anuncio_privado")
async def anuncio_contratos_privado(ctx):
    """Envía la lista de contratos por mensaje privado"""
    try:
        contratos = get_contratos()
        
        if not contratos:
            mensaje = "🔄 ** CONTRATOS DISPONIBLES:** 🔄\n\n**📋 CONTRATOS DISPONIBLES:**\n\n❌ **No hay contratos disponibles en este momento.**\n\n---\n💼 **Total de contratos activos: 0**"
        else:
            mensaje = "🔄 ** CONTRATOS DISPONIBLES:** 🔄\n\n**📋 CONTRATOS DISPONIBLES:**\n\n"
            
            for i, (nombre, enlace) in enumerate(contratos, 1):
                mensaje += f"**{i}.** **{nombre}**\n{enlace}\n\n"
            
            mensaje += f"---\n💼 **Total de contratos activos: {len(contratos)}**"
        
        # Enviar por mensaje privado
        await ctx.author.send(mensaje)
        await ctx.send("✅ Lista de contratos enviada por mensaje privado.")
        
    except Exception as e:
        await ctx.send(f"❌ Error al enviar mensaje privado: {e}")

bot.run(TOKEN)

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime
import re
import json

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="//", intents=intents)

# =========================
# DATOS
# =========================
banco = {}  # inventario global
registro_usuarios = {}  # {user_id: {item: cantidad acumulada}}
historial_usuarios = {}  # {user_id: [(timestamp, accion, item, cantidad, ubicacion)]}
reputacion = {}  # {user_id: puntos}

iconos = {
    "pepinos": "🥒", "scu iron": "⛓️", "agricium": "🪨", "aluminium": "🪨",
    "aphorite": "🪨", "bexalite": "🪨", "borase": "🪨", "copper": "🪨",
    "corundum": "🪨", "diamond": "💎", "dolivine": "🪨", "gold": "🟡",
    "hadanite": "🪨", "laranite": "🟣", "levskiite": "🪨", "quantanium": "⚠️",
    "taranite": "🪨", "titanium": "🪨", "zetaprolium": "🪨",
    "p8": "🔫", "p4-ar": "🔫", "p5-ar": "🔫", "p6-ar": "🔫", "p7-ar": "🔫", "p8-ar": "🔫",
    "arclight": "🔫", "lh86": "🔫", "s-38": "🔫", "br-2": "🔫", "devastator": "🔫",
    "f55": "🔫", "fs-9": "🔫", "demeco": "🔫", "scourge": "🔫", "salvo frag": "🔫",
    "armaduras corvus": "🛡️", "armadura ligera": "🛡️", "armadura media": "🛡️",
    "armadura pesada": "🛡️", "armadura radiación": "☢️", "armadura calor": "🔥", "armadura frío": "❄️",
    "alimentos": "🍽️", "agua": "🥤", "medpen": "💊"
}

categorias = {
    "Consumibles": ["alimentos", "agua", "pepinos"],
    "Minerales y materiales": ["scu iron","agricium","aluminium","aphorite","bexalite","borase","copper","corundum","diamond","dolivine","gold","hadanite","laranite","levskiite","quantanium","taranite","titanium","zetaprolium"],
    "Armas": ["p4-ar","p5-ar","p6-ar","p7-ar","p8-ar","p8","arclight","lh86","s-38","br-2","devastator","f55","fs-9","demeco","scourge","salvo frag"],
    "Armaduras": ["armaduras corvus","armadura ligera","armadura media","armadura pesada","armadura radiación","armadura calor","armadura frío"],
    "Medicinas": ["medpen"],
    "Otros": []
}

limites = {
    "default": 50,
    "Minerales y materiales": 1000
}

# Cargar sistema de búsqueda de objetos
try:
    with open('sistema_busqueda_objetos.json', 'r', encoding='utf-8') as f:
        sistema_busqueda = json.load(f)
    print(f"Sistema de búsqueda cargado con {len(sistema_busqueda)} objetos")
except FileNotFoundError:
    sistema_busqueda = {}
    print("⚠️ Sistema de búsqueda no encontrado. Usando sistema básico.")

# =========================
# FUNCIONES AUXILIARES
# =========================
def normalizar(nombre):
    return nombre.lower()

def calcular_reputacion(cat, cantidad):
    if cat=="Armas": return 0.05*cantidad
    if cat=="Armaduras": return 0.2*cantidad
    if cat=="Consumibles": return 0.01*cantidad
    if cat=="Medicinas": return 0.02*cantidad
    if cat=="Minerales y materiales": return 0.05*(cantidad/10)
    return 0.01*cantidad

def registrar_historial(user_id, accion, item, cantidad, ubicacion=None, usuario_relacionado=None):
    historial_usuarios.setdefault(user_id, [])
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    historial_usuarios[user_id].append((timestamp, accion, item, cantidad, ubicacion, usuario_relacionado))

def obtener_limite(item):
    for cat, items in categorias.items():
        if item in items:
            return limites.get(cat, limites["default"])
    return limites["default"]

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

def buscar_objetos(termino_busqueda, limite=25):
    """Busca objetos que coincidan con el término de búsqueda"""
    if not sistema_busqueda:
        return []
    
    termino = termino_busqueda.lower().strip()
    if not termino:
        return []
    
    resultados = []
    for nombre_normalizado, datos in sistema_busqueda.items():
        if termino in nombre_normalizado:
            resultados.append({
                'nombre': datos['nombre_original'],
                'categoria': datos['categoria']
            })
    
    # Ordenar por relevancia (coincidencias al inicio)
    resultados.sort(key=lambda x: x['nombre'].lower().startswith(termino), reverse=True)
    return resultados[:limite]

def buscar_objetos_inventario(termino_busqueda, user_id, limite=25):
    """Busca objetos que coincidan con el término de búsqueda y que estén en el inventario del usuario"""
    if not sistema_busqueda:
        return []
    
    termino = termino_busqueda.lower().strip()
    if not termino:
        return []
    
    # Obtener objetos del usuario
    inventario_usuario = registro_usuarios.get(user_id, {})
    objetos_disponibles = [nombre for nombre, cantidad in inventario_usuario.items() if cantidad > 0]
    
    resultados = []
    for nombre_normalizado, datos in sistema_busqueda.items():
        if termino in nombre_normalizado:
            nombre_original = datos['nombre_original']
            # Verificar si el usuario tiene este objeto
            if nombre_original in objetos_disponibles:
                cantidad_usuario = inventario_usuario[nombre_original]
                resultados.append({
                    'nombre': nombre_original,
                    'categoria': datos['categoria'],
                    'cantidad': cantidad_usuario
                })
    
    # Ordenar por relevancia (coincidencias al inicio)
    resultados.sort(key=lambda x: x['nombre'].lower().startswith(termino), reverse=True)
    return resultados[:limite]

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
# EVENTO BOT READY
# =========================
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user} (id: {bot.user.id})")

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
        self.ubicacion_input = discord.ui.TextInput(
            label="Ubicación (solo para añadir)",
            placeholder="Ej: Terra, New Babbage...",
            required=(tipo == "añadir"),
            max_length=100
        )
        self.add_item(self.cantidad_input)
        self.add_item(self.busqueda_input)
        if tipo == "añadir":
            self.add_item(self.ubicacion_input)

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
        
        # Si hay muchos resultados, mostrar selección
        if len(resultados) > 1:
            await self.mostrar_seleccion(interaction, resultados, cantidad)
        else:
            # Un solo resultado, procesar directamente
            objeto_seleccionado = resultados[0]
            await self.procesar_objeto(interaction, objeto_seleccionado, cantidad)
    
    async def mostrar_seleccion(self, interaction, resultados, cantidad):
        # Obtener el término de búsqueda del input
        termino_busqueda = self.busqueda_input.value.strip()
        
        class SeleccionObjetoView(discord.ui.View):
            def __init__(self, resultados, cantidad, tipo, ubicacion=None):
                super().__init__(timeout=60)
                self.resultados = resultados
                self.cantidad = cantidad
                self.tipo = tipo
                self.ubicacion = ubicacion
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
                    
                    # Crear callback específico para este botón
                    async def button_callback(interaction, obj=resultado):
                        await self.seleccionar_objeto(interaction, obj)
                    
                    button.callback = button_callback
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
                categoria_existente = None
                for cat, items in categorias.items():
                    if nombre.lower() in [item.lower() for item in items]:
                        categoria_existente = cat
                        break
                
                # Si no existe, agregarlo a la categoría correspondiente
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
                    categorias[categoria_bot].append(nombre)
                    categoria_existente = categoria_bot
                
                # Procesar añadir
                limite = obtener_limite(nombre)
                cantidad_actual = banco.get(nombre, 0)
                cantidad_posible = min(cantidad, limite - cantidad_actual)
                
                if cantidad_posible <= 0:
                    await interaction.followup.send(f"❌ El almacén para {nombre} está lleno. No se ha añadido nada.", ephemeral=True)
                    return
                
                banco[nombre] = cantidad_actual + cantidad_posible
                registro_usuarios.setdefault(interaction.user.id, {})
                registro_usuarios[interaction.user.id][nombre] = registro_usuarios[interaction.user.id].get(nombre, 0) + cantidad_posible
                registrar_historial(interaction.user.id, "Añadido", nombre, cantidad_posible, self.ubicacion)
                
                ganado = calcular_reputacion(categoria_existente, cantidad_posible)
                reputacion[interaction.user.id] = reputacion.get(interaction.user.id, 0) + ganado
                registrar_historial(interaction.user.id, "Ganó Reputación", "Reputación", ganado)
                
                mensaje_respuesta = f"✅ {interaction.user.mention} añadió {cantidad_posible} de {nombre} ({categoria_existente}).\nUbicación registrada en tu historial.\nGanaste **{ganado:.2f}** :ReputacionCorvus:. Total: **{reputacion[interaction.user.id]:.2f}**"
                if cantidad_posible < cantidad:
                    mensaje_respuesta += f"\n⚠️ Solo se pudieron añadir {cantidad_posible} debido al límite de almacenamiento."
                
                await interaction.followup.send(mensaje_respuesta, ephemeral=True)
                # Mostrar botonera después de completar la acción
                view = BotoneraView()
                await interaction.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
            
            async def procesar_retirar(self, interaction, objeto, cantidad):
                nombre = objeto['nombre']
                
                # Verificar disponibilidad
                if nombre not in banco or registro_usuarios.get(interaction.user.id, {}).get(nombre, 0) < cantidad:
                    await interaction.followup.send("❌ No tienes suficiente cantidad o el objeto no existe.", ephemeral=True)
                    return
                
                banco[nombre] -= cantidad
                registro_usuarios[interaction.user.id][nombre] -= cantidad
                registrar_historial(interaction.user.id, "Retirado", nombre, -cantidad)
                await interaction.followup.send(f"✅ Retiraste {cantidad} de {nombre}.", ephemeral=True)
                # Mostrar botonera después de completar la acción
                view = BotoneraView()
                await interaction.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
        
        ubicacion = self.ubicacion_input.value.strip() if self.tipo == "añadir" else None
        view = SeleccionObjetoView(resultados, cantidad, self.tipo, ubicacion)
        
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
        ubicacion = self.ubicacion_input.value.strip()
        
        # Verificar si el objeto ya existe en categorías
        categoria_existente = None
        for cat, items in categorias.items():
            if nombre.lower() in [item.lower() for item in items]:
                categoria_existente = cat
                break
        
        # Si no existe, agregarlo a la categoría correspondiente
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
            categorias[categoria_bot].append(nombre)
            categoria_existente = categoria_bot
        
        # Procesar añadir
        limite = obtener_limite(nombre)
        cantidad_actual = banco.get(nombre, 0)
        cantidad_posible = min(cantidad, limite - cantidad_actual)
        
        if cantidad_posible <= 0:
            await interaction.response.send_message(f"❌ El almacén para {nombre} está lleno. No se ha añadido nada.", ephemeral=True)
            return
        
        banco[nombre] = cantidad_actual + cantidad_posible
        registro_usuarios.setdefault(interaction.user.id, {})
        registro_usuarios[interaction.user.id][nombre] = registro_usuarios[interaction.user.id].get(nombre, 0) + cantidad_posible
        registrar_historial(interaction.user.id, "Añadido", nombre, cantidad_posible, ubicacion)
        
        ganado = calcular_reputacion(categoria_existente, cantidad_posible)
        reputacion[interaction.user.id] = reputacion.get(interaction.user.id, 0) + ganado
        registrar_historial(interaction.user.id, "Ganó Reputación", "Reputación", ganado)
        
        mensaje_respuesta = f"✅ {interaction.user.mention} añadió {cantidad_posible} de {nombre} ({categoria_existente}).\nUbicación registrada en tu historial.\nGanaste **{ganado:.2f}** :ReputacionCorvus:. Total: **{reputacion[interaction.user.id]:.2f}**"
        if cantidad_posible < cantidad:
            mensaje_respuesta += f"\n⚠️ Solo se pudieron añadir {cantidad_posible} debido al límite de almacenamiento."
        
        await interaction.response.send_message(mensaje_respuesta, ephemeral=True)
        # Mostrar botonera después de completar la acción
        view = BotoneraView()
        await interaction.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
    
    async def procesar_retirar(self, interaction, objeto, cantidad):
        nombre = objeto['nombre']
        
        # Verificar disponibilidad
        if nombre not in banco or registro_usuarios.get(interaction.user.id, {}).get(nombre, 0) < cantidad:
            await interaction.response.send_message("❌ No tienes suficiente cantidad o el objeto no existe.", ephemeral=True)
            return
        
        banco[nombre] -= cantidad
        registro_usuarios[interaction.user.id][nombre] -= cantidad
        registrar_historial(interaction.user.id, "Retirado", nombre, -cantidad)
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
        historial_usuario = historial_usuarios.get(interaction.user.id, [])
        if not historial_usuario:
            await interaction.response.send_message("No tienes historial.", ephemeral=True)
        else:
            mensaje="**📜 Historial de tus operaciones**\n"
            for entrada in historial_usuario:
                if len(entrada) == 6:  # Formato nuevo con usuario_relacionado
                    ts, accion, item, cant, ubic, usuario_rel = entrada
                    ubic_txt = f" (Ubicación: {ubic})" if ubic else ""
                    usuario_txt = f" → {usuario_rel}" if usuario_rel and accion in ["Transferido", "Recibido"] else f" ← {usuario_rel}" if usuario_rel else ""
                    mensaje+=f"[{ts}] {accion}: {item} ({cant}){ubic_txt}{usuario_txt}\n"
                else:  # Formato antiguo (compatibilidad)
                    ts, accion, item, cant, ubic = entrada
                    ubic_txt = f" (Ubicación: {ubic})" if ubic else ""
                    mensaje+=f"[{ts}] {accion}: {item} ({cant}){ubic_txt}\n"
            await interaction.response.send_message(mensaje, ephemeral=True)
        await self.volver_menu(interaction)

    # -----------------
    # TRANSFERIR
    # -----------------
    @discord.ui.button(label="Transferir", style=discord.ButtonStyle.blurple)
    async def transferir_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        class TransferirTipoView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="Reputación", style=discord.ButtonStyle.green)
            async def reputacion_btn(self, interaction2: discord.Interaction, button2: discord.ui.Button):
                # Modal combinado para reputación
                class ReputacionTransferModal(discord.ui.Modal, title="Transferir Reputación"):
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
                        cantidad = float(cantidad_texto)
                        
                        if reputacion.get(interaction.user.id,0)<cantidad:
                            await interaction.response.send_message("❌ No tienes suficiente reputación.", ephemeral=True)
                            return
                        
                        await interaction.response.defer(ephemeral=True)
                        
                        class RecipientSelect(discord.ui.UserSelect):
                            def __init__(self):
                                super().__init__(placeholder="Elige destinatario", min_values=1, max_values=1)
                            async def callback(self, i: discord.Interaction):
                                usuario = self.values[0]
                                reputacion[interaction.user.id]-=cantidad
                                reputacion[usuario.id]=reputacion.get(usuario.id,0)+cantidad
                                registrar_historial(interaction.user.id, "Transferido", "Reputación", -cantidad, usuario_relacionado=usuario.name)
                                registrar_historial(usuario.id, "Recibido", "Reputación", cantidad, usuario_relacionado=interaction.user.name)
                                await i.response.send_message(f"✅ Transferidos {cantidad:.2f} :ReputacionCorvus: a {usuario.mention}", ephemeral=True)
                                await BotoneraView().volver_menu(interaction)
                        
                        class RecipientSelectView(discord.ui.View):
                            def __init__(self):
                                super().__init__(timeout=60)
                                self.add_item(RecipientSelect())
                        
                        await interaction.followup.send("Selecciona el destinatario:", view=RecipientSelectView(), ephemeral=True)
                
                modal = ReputacionTransferModal()
                await interaction2.response.send_modal(modal)

            @discord.ui.button(label="Material", style=discord.ButtonStyle.blurple)
            async def material_btn(self, interaction2: discord.Interaction, button2: discord.ui.Button):
                # Modal con sistema de búsqueda inteligente para transferencia de material
                class MaterialTransferModal(discord.ui.Modal, title="Transferir Material"):
                    def __init__(self):
                        super().__init__()
                        self.cantidad_input = discord.ui.TextInput(
                            label="Cantidad a transferir",
                            placeholder="Ej: 10",
                            required=True,
                            max_length=10
                        )
                        self.busqueda_input = discord.ui.TextInput(
                            label="Buscar objeto a transferir",
                            placeholder="Escribe para buscar (ej: p4, scu iron...)",
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
                        
                        # Buscar objetos en el inventario del usuario
                        termino_busqueda = self.busqueda_input.value.strip()
                        resultados = buscar_objetos_inventario(termino_busqueda, interaction.user.id, 25)
                        
                        if not resultados:
                            await interaction.response.send_message(f"❌ No se encontraron objetos que coincidan con '{termino_busqueda}' en tu inventario. Verifica el nombre o intenta con un término más general.", ephemeral=True)
                            return
                        
                        # Si hay muchos resultados, mostrar selección
                        if len(resultados) > 1:
                            await self.mostrar_seleccion(interaction, resultados, cantidad)
                        else:
                            objeto_seleccionado = resultados[0]
                            await self.procesar_transferencia(interaction, objeto_seleccionado, cantidad)
                    
                    async def mostrar_seleccion(self, interaction, resultados, cantidad):
                        termino_busqueda = self.busqueda_input.value.strip()  # Obtener el término de búsqueda
                        
                        class SeleccionTransferView(discord.ui.View):
                            def __init__(self, resultados, cantidad):
                                super().__init__(timeout=60)
                                self.resultados = resultados
                                self.cantidad = cantidad
                                self.used = False
                                
                                # Crear botones para cada resultado
                                for i, resultado in enumerate(resultados[:25]):
                                    label = resultado['nombre'][:80]
                                    if len(resultado['nombre']) > 80:
                                        label += "..."
                                    
                                    button = discord.ui.Button(
                                        label=f"{i+1}. {label}",
                                        style=discord.ButtonStyle.secondary,
                                        custom_id=f"select_{i}"
                                    )
                                    
                                    # Crear callback específico para este botón
                                    async def button_callback(interaction, obj=resultado):
                                        await self.seleccionar_objeto(interaction, obj)
                                    
                                    button.callback = button_callback
                                    self.add_item(button)
                            
                            async def seleccionar_objeto(self, interaction, objeto):
                                if self.used:
                                    await interaction.response.send_message("Esta selección ya fue usada. Inicia de nuevo el proceso.", ephemeral=True)
                                    return
                                self.used = True
                                
                                try:
                                    await interaction.message.delete()
                                except Exception:
                                    pass
                                
                                await interaction.response.defer(ephemeral=True)
                                await self.procesar_transferencia(interaction, objeto, self.cantidad)
                            
                            async def procesar_transferencia(self, interaction, objeto, cantidad):
                                nombre = objeto['nombre']
                                
                                if nombre not in registro_usuarios.get(interaction.user.id, {}) or registro_usuarios[interaction.user.id][nombre] < cantidad:
                                    await interaction.followup.send("❌ No tienes suficiente cantidad o el objeto no existe.", ephemeral=True)
                                    return
                                
                                class RecipientSelect(discord.ui.UserSelect):
                                    def __init__(self):
                                        super().__init__(placeholder="Elige destinatario", min_values=1, max_values=1)
                                    
                                    async def callback(self, i: discord.Interaction):
                                        usuario = self.values[0]
                                        registro_usuarios[interaction.user.id][nombre] -= cantidad
                                        registro_usuarios.setdefault(usuario.id, {})
                                        registro_usuarios[usuario.id][nombre] = registro_usuarios[usuario.id].get(nombre, 0) + cantidad
                                        banco[nombre] = banco.get(nombre, 0)
                                        registrar_historial(interaction.user.id, "Transferido", nombre, -cantidad, usuario_relacionado=usuario.name)
                                        registrar_historial(usuario.id, "Recibido", nombre, cantidad, usuario_relacionado=interaction.user.name)
                                        await i.response.send_message(f"✅ Transferidos {cantidad} de {nombre} a {usuario.mention}", ephemeral=True)
                                        view = BotoneraView()
                                        await i.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
                                
                                class RecipientSelectView(discord.ui.View):
                                    def __init__(self):
                                        super().__init__(timeout=60)
                                        self.add_item(RecipientSelect())
                                
                                await interaction.followup.send("Selecciona el destinatario:", view=RecipientSelectView(), ephemeral=True)
                        
                        view = SeleccionTransferView(resultados, cantidad)
                        
                        # Crear mensaje con los resultados
                        mensaje = f"🔍 **Resultados para '{termino_busqueda}'** ({len(resultados)} encontrados):\n\n"
                        for i, resultado in enumerate(resultados[:25], 1):
                            mensaje += f"**{i}.** {resultado['nombre']} ({resultado['categoria']}) - Disponible: {resultado['cantidad']}\n"
                        
                        if len(resultados) > 25:
                            mensaje += f"\n... y {len(resultados) - 25} más. Usa un término más específico."
                        
                        mensaje += f"\n\nSelecciona el objeto que quieres transferir:"
                        
                        await interaction.response.send_message(mensaje, view=view, ephemeral=True)
                    
                    async def procesar_transferencia(self, interaction, objeto, cantidad):
                        nombre = objeto['nombre']
                        
                        if nombre not in registro_usuarios.get(interaction.user.id, {}) or registro_usuarios[interaction.user.id][nombre] < cantidad:
                            await interaction.response.send_message("❌ No tienes suficiente cantidad o el objeto no existe.", ephemeral=True)
                            return
                        
                        class RecipientSelect(discord.ui.UserSelect):
                            def __init__(self):
                                super().__init__(placeholder="Elige destinatario", min_values=1, max_values=1)
                            
                            async def callback(self, i: discord.Interaction):
                                usuario = self.values[0]
                                registro_usuarios[interaction.user.id][nombre] -= cantidad
                                registro_usuarios.setdefault(usuario.id, {})
                                registro_usuarios[usuario.id][nombre] = registro_usuarios[usuario.id].get(nombre, 0) + cantidad
                                banco[nombre] = banco.get(nombre, 0)
                                registrar_historial(interaction.user.id, "Transferido", nombre, -cantidad, usuario_relacionado=usuario.name)
                                registrar_historial(usuario.id, "Recibido", nombre, cantidad, usuario_relacionado=interaction.user.name)
                                await i.response.send_message(f"✅ Transferidos {cantidad} de {nombre} a {usuario.mention}", ephemeral=True)
                                view = BotoneraView()
                                await i.followup.send("Selecciona una opción del menú:", view=view, ephemeral=True)
                        
                        class RecipientSelectView(discord.ui.View):
                            def __init__(self):
                                super().__init__(timeout=60)
                                self.add_item(RecipientSelect())
                        
                        await interaction.response.send_message("Selecciona el destinatario:", view=RecipientSelectView(), ephemeral=True)
                
                modal = MaterialTransferModal()
                await interaction2.response.send_modal(modal)

        view = TransferirTipoView()
        await interaction.response.send_message("Selecciona qué quieres transferir:", view=view, ephemeral=True)

    # -----------------
    # INVENTARIO
    # -----------------
    @discord.ui.button(label="Inventario", style=discord.ButtonStyle.primary)
    async def inventario_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not banco:
            await interaction.response.send_message("📦 Inventario vacío.", ephemeral=True)
            await self.volver_menu(interaction)
            return
        mensaje = "**📦 Banco del clan — Inventario**\n\n"
        for cat, items in categorias.items():
            if not items: continue
            emoji_cat = {"Consumibles":"🍽️","Minerales y materiales":"🪨","Armas":"🔫","Armaduras":"🛡️","Medicinas":"💊","Otros":"📦"}.get(cat,"📦")
            mensaje+=f"**__{emoji_cat} {cat}__**\n"
            for item in items:
                if item in banco and banco[item]>0:
                    icono=iconos.get(item,"📦")
                    limite_item = obtener_limite(item)
                    detalles = []
                    for uid, inv in registro_usuarios.items():
                        if item in inv and inv[item]>0:
                            user = await bot.fetch_user(uid)
                            detalles.append(f"{user.name} {inv[item]}")
                    barra = barra_progreso(banco[item], limite_item)
                    reparto = ", ".join(detalles)
                    if reparto:
                        mensaje+=f"{icono} {item} — {banco[item]}/{limite_item} {barra} | {reparto}\n"
                    else:
                        mensaje+=f"{icono} {item} — {banco[item]}/{limite_item} {barra}\n"
        await interaction.response.send_message(mensaje, ephemeral=True)
        await self.volver_menu(interaction)

    # -----------------
    # RANKING
    # -----------------
    @discord.ui.button(label="Ranking", style=discord.ButtonStyle.secondary)
    async def ranking_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        top = sorted(reputacion.items(), key=lambda x: x[1], reverse=True)
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
        puntos = reputacion.get(interaction.user.id,0)
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

# =========================
# COMANDO PARA MOSTRAR BOTONERA
# =========================
@bot.command(name="menu")
async def menu(ctx):
    view = BotoneraView()
    await ctx.send("Selecciona una opción del menú:", view=view)

bot.run(TOKEN)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sabor Sabanero S.A.S. - Sistema de Optimización de Flotas y Cadena de Frío
Desarrollado para la distribución en la Sabana de Bogotá.
"""
import math
import itertools
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN GEOGRÁFICA Y DATOS DE ENTRADA ---
# CEDI principal en Tocancipá (Origen / Fin)
CEDI_TOCANCIPA = {
    "id": "tocancipa",
    "nombre": "CEDI Tocancipá",
    "lat": 4.964,
    "lng": -73.912,
    "demanda": 0,
    "descarga": 0,
    "color": "Green"
}

# Clientes preconfigurados con coordenadas, demanda (kg) y tiempo de descarga (minutos)
BASE_CLIENTES = [
    {"id": "chia", "nombre": "Chía", "lat": 4.863, "lng": -74.053, "demanda": 1100, "descarga": 25},
    {"id": "cajica", "nombre": "Cajicá", "lat": 4.918, "lng": -74.029, "demanda": 750, "descarga": 15},
    {"id": "zipaquira", "nombre": "Zipaquirá", "lat": 4.996, "lng": -74.003, "demanda": 1400, "descarga": 30},
    {"id": "sopo", "nombre": "Sopó", "lat": 4.908, "lng": -73.938, "demanda": 900, "descarga": 15},
    {"id": "briceno", "nombre": "Briceño", "lat": 4.945, "lng": -73.921, "demanda": 500, "descarga": 10}
]

# Parámetros físicos e infraestructura de la flota
TRUCK_CAPACITY = 2200         # kg máxima por vehículo (Q_k)
MAX_TRUCKS = 3                # Camiones idénticos en flota
SCALE_FACTOR_KM_DEGREE = 111.0 # SF constante para la Sabana de Bogotá
VELOCIDAD_PROMEDIO_KMH = 45.0  # km/h considerando el tráfico de la Sabana

# --- 2. UTILIDADES DE CÁLCULO ---
def calcular_distancia_km(p1, p2):
    """
    Calcula la distancia euclidiana entre dos puntos usando el factor de escala
    SF = 111,000 m/grado (111.0 km/grado)
    """
    dy = p1["lat"] - p2["lat"]
    dx = p1["lng"] - p2["lng"]
    return math.sqrt(dx**2 + dy**2) * SCALE_FACTOR_KM_DEGREE

def convertir_hora_a_minutos(hora_str):
    """Convierte un string 'HH:MM' a minutos desde la medianoche."""
    t = datetime.strptime(hora_str, "%H:%M")
    return t.hour * 60 + t.minute

def convertir_minutos_a_hora(minutos):
    """Convierte minutos totales a string con formato 'HH:MM'."""
    minutos_mod = int(minutos % 1440)
    horas = minutos_mod // 60
    mins = minutos_mod % 60
    return f"{horas:02d}:{mins:02d}"

# --- 3. ALGORITMOS DE OPTIMIZACIÓN (VRP & TSP) ---
def verificar_viabilidad_flota(clientes, capacidad_max, max_camiones):
    """Valida si la flota tiene la capacidad total para cubrir la demanda."""
    demanda_total = sum(c["demanda"] for c in clientes)
    capacidad_total = capacidad_max * max_camiones
    if demanda_total > capacidad_total:
        print(f"⚠️  ALERTA CRÍTICA: La demanda total ({demanda_total} kg) excede la capacidad de la flota ({capacidad_total} kg).")
        return False
    return True

def resolver_vrp(clientes, capacidad_max):
    """
    Agrupa los clientes en rutas respetando la restricción de capacidad (Q_k)
    utilizando una heurística First-Fit Decreasing basada en la demanda.
    """
    # Ordenar clientes de mayor a menor demanda para optimizar el empaquetado
    clientes_ordenados = sorted(clientes, key=lambda c: c["demanda"], reverse=True)
    rutas = []
    
    for cliente in clientes_ordenados:
        asignado = False
        for r in rutas:
            carga_actual = sum(c["demanda"] for c in r)
            if carga_actual + cliente["demanda"] <= capacidad_max:
                r.append(cliente)
                asignado = True
                break
        if not asignado:
            rutas.append([cliente])

    # Optimizar el orden secuencial (TSP) para cada ruta asignada
    rutas_optimizadas = []
    for r in rutas:
        rutas_optimizadas.append(optimizar_tsp_local(r))

    return rutas_optimizadas

def optimizar_tsp_local(sub_ruta):
    """
    Encuentra el recorrido óptimo (TSP) para un grupo de clientes de un furgón.
    Al ser un número reducido de nodos (< 5 por camión), se evalúan todas las permutaciones.
    """
    if len(sub_ruta) <= 1:
        return sub_ruta
    mejor_secuencia = list(sub_ruta)
    menor_distancia = float("inf")
    
    # Evaluar todas las permutaciones posibles de visita
    for perm in itertools.permutations(sub_ruta):
        distancia_actual = calcular_distancia_circuito(perm)
        if distancia_actual < menor_distancia:
            menor_distancia = distancia_actual
            mejor_secuencia = list(perm)
    return mejor_secuencia

def calcular_distancia_circuito(secuencia):
    """Calcula la distancia total ida y vuelta de un circuito (CEDI -> Secuencia -> CEDI)"""
    distancia = 0
    actual = CEDI_TOCANCIPA
    for cliente in secuencia:
        distancia += calcular_distancia_km(actual, cliente)
        actual = cliente
    distancia += calcular_distancia_km(actual, CEDI_TOCANCIPA)
    return distancia

# --- 4. SIMULACIÓN TERMODINÁMICA DE CADENA DE FRÍO ---
def simular_ruta_vehiculo(clientes_sub_ruta, id_camion, config):
    """
    Simula el progreso en el tiempo y el comportamiento térmico del furgón.
    Utiliza la ley de enfriamiento de Newton para la conducción y pérdidas por apertura.
    """
    hora_salida_min = convertir_hora_a_minutos(config["hora_salida"])
    temp_ambiente = config["temp_ambiente"]
    temp_inicial = config["temp_inicial"]
    k_aislamiento = config["coef_aislamiento"]
    perdida_puerta = config["perdida_puerta"]
    
    tiempo_actual_min = hora_salida_min
    temp_furgon = temp_inicial
    distancia_acumulada = 0.0
    itinerario = []
    
    # Registro de salida del CEDI
    itinerario.append({
        "punto": CEDI_TOCANCIPA["nombre"],
        "llegada": convertir_minutos_a_hora(tiempo_actual_min),
        "distancia_tramo": 0.0,
        "distancia_total": 0.0,
        "accion": "Despacho y Carga de Lácteos",
        "duracion_accion": 0,
        "temp_furgon": temp_furgon,
        "estado": "Óptimo"
    })
    
    actual_nodo = CEDI_TOCANCIPA
    for cliente in clientes_sub_ruta:
        # 1. Tránsito / Conducción hacia el cliente
        dist = calcular_distancia_km(actual_nodo, cliente)
        distancia_acumulada += dist
        tiempo_viaje_min = round((dist / VELOCIDAD_PROMEDIO_KMH) * 60)
        
        # Pérdida térmica por conducción en movimiento
        horas_viaje = tiempo_viaje_min / 60.0
        temp_furgon = temp_ambiente - (temp_ambiente - temp_furgon) * math.exp(-k_aislamiento * horas_viaje)
        tiempo_actual_min += tiempo_viaje_min
        
        # 2. Llegada y Apertura de compuerta (Pérdida por choque térmico instantáneo)
        temp_furgon += perdida_puerta

        # Desgaste de frío continuo durante la descarga
        horas_descarga = cliente["descarga"] / 60.0
        k_puerta_abierta = k_aislamiento * 3.5  # Transferencia térmica acelerada por aire exterior
        temp_furgon = temp_ambiente - (temp_ambiente - temp_furgon) * math.exp(-k_puerta_abierta * horas_descarga)
        temp_furgon = round(temp_furgon, 1)
        
        # Evaluar estado de temperatura (Ideal: 2°C - 4°C, Crítico: > 6°C)
        if temp_furgon > 6.0:
            estado = "CRÍTICO (>6°C)"
        elif temp_furgon > 4.0:
            estado = "ADVERTENCIA"
        else:
            estado = "ÓPTIMO"
            
        itinerario.append({
            "punto": cliente["nombre"],
            "llegada": convertir_minutos_a_hora(tiempo_actual_min),
            "distancia_tramo": round(dist, 1),
            "distancia_total": round(distancia_acumulada, 1),
            "accion": f"Entrega: {cliente['demanda']} kg",
            "duracion_accion": cliente["descarga"],
            "temp_furgon": temp_furgon,
            "estado": estado
        })
        tiempo_actual_min += cliente["descarga"]
        actual_nodo = cliente
        
    # 3. Retorno al CEDI
    dist_retorno = calcular_distancia_km(actual_nodo, CEDI_TOCANCIPA)
    distancia_acumulada += dist_retorno
    tiempo_retorno_min = round((dist_retorno / VELOCIDAD_PROMEDIO_KMH) * 60)
    
    # Pérdida térmica en el tramo final de regreso
    horas_retorno = tiempo_retorno_min / 60.0
    temp_furgon = temp_ambiente - (temp_ambiente - temp_furgon) * math.exp(-k_aislamiento * horas_retorno)
    temp_furgon = round(temp_furgon, 1)
    tiempo_actual_min += tiempo_retorno_min
    
    itinerario.append({
        "punto": CEDI_TOCANCIPA["nombre"],
        "llegada": convertir_minutos_a_hora(tiempo_actual_min),
        "distancia_tramo": round(dist_retorno, 1),
        "distancia_total": round(distancia_acumulada, 1),
        "accion": "Cierre de Ruta y Retorno",
        "duracion_accion": 0,
        "temp_furgon": temp_furgon,
        "estado": "CRÍTICO" if temp_furgon > 6.0 else ("ADVERTENCIA" if temp_furgon > 4.0 else "ÓPTIMO")
    })
    
    return {
        "id_camion": id_camion,
        "itinerario": itinerario,
        "distancia_total": round(distancia_acumulada, 1),
        "carga_total": sum(c["demanda"] for c in clientes_sub_ruta),
        "tiempo_total_min": tiempo_actual_min - hora_salida_min,
        "temp_final": temp_furgon,
        "clientes": [c["nombre"] for c in clientes_sub_ruta]
    }

# --- 5. VISUALIZACIÓN EN CONSOLA (REPORTE) ---
def imprimir_reporte_flota(asignaciones):
    """Muestra un reporte estructurado y elegante en consola con los KPIs de distribución."""
    print("=" * 85)
    print("               SABOR SABANERO S.A.S. - REPORTE DE RUTAS Y CADENA DE FRÍO")
    print("=" * 85)

    total_distancia = 0.0
    total_carga = 0
    camiones_activos = len(asignaciones)
    
    for viaje in asignaciones:
        total_distancia += viaje["distancia_total"]
        total_carga += viaje["carga_total"]

        horas_viaje = viaje["tiempo_total_min"] // 60
        mins_viaje = viaje["tiempo_total_min"] % 60
        print(f"\n 🚚  CAMIÓN 0{viaje['id_camion'] + 1} | Clientes: {'  ➔  '.join(viaje['clientes'])}")
        print(f"   • Carga Útil: {viaje['carga_total']} kg / {TRUCK_CAPACITY} kg")
        print(f"   • Recorrido: {viaje['distancia_total']} km")
        print(f"   • Duración Estimada: {horas_viaje} h {mins_viaje} min")
        print(f"   • Temp. Retorno CEDI: {viaje['temp_final']} °C")
        print("-" * 85)

        # Cabecera de tabla de paradas
        print(f"   {'Punto / Destino':<20} | {'Llegada':<8} | {'Operación / Acción':<24} | {'Parada':<7} | {'Temp. Furgón':<12}")
        print(f"   {'-'*20}-+-{'-'*8}-+-{'-'*24}-+-{'-'*7}-+-{'-'*12}")

        for p in viaje["itinerario"]:
            duracion_str = f"{p['duracion_accion']} min" if p["duracion_accion"] > 0 else "--"
            temp_str = f"{p['temp_furgon']} °C ({p['estado']})"
            print(f"   {p['punto']:<20} | {p['llegada']:<8} | {p['accion']:<24} | {duracion_str:<7} | {temp_str:<12}")
        print("=" * 85)
        
    print("\n 📊  RESUMEN GENERAL DE LA FLOTA:")
    print(f"   • Camiones Utilizados : {camiones_activos} de {MAX_TRUCKS} disponibles")
    print(f"   • Carga Total Entregada: {total_carga} kg")
    print(f"   • Recorrido Total Flota: {total_distancia:.1f} km")
    print("=" * 85)

# --- 6. VISUALIZACIÓN GEOGRÁFICA (OPCIONAL) ---
def graficar_rutas_sabanera(asignaciones):
    """
    Genera un plano bidimensional con las posiciones geográficas reales
    y los trazados independientes de cada camión si matplotlib está instalado.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n 💡  Nota: Para visualizar el plano geográfico interactivo de la Sabana de Bogotá,")
        print("          instale matplotlib ejecutando: 'pip install matplotlib'")
        return
        
    plt.figure(figsize=(9, 7))
    plt.style.use('dark_background')

    # Dibujar CEDI Tocancipá
    plt.plot(CEDI_TOCANCIPA["lng"], CEDI_TOCANCIPA["lat"], 'gH', markersize=14, label="CEDI Tocancipá (Base)")
    plt.text(CEDI_TOCANCIPA["lng"] + 0.003, CEDI_TOCANCIPA["lat"] + 0.003, "CEDI Tocancipá", color='lightgreen', fontweight='bold')
    
    # Paleta de colores para cada camión
    colores_camion = ['#38bdf8', '#c084fc', '#facc15']
    
    for idx, viaje in enumerate(asignaciones):
        color = colores_camion[idx % len(colores_camion)]

        # Construir coordenadas secuenciales de la ruta
        latitudes = [CEDI_TOCANCIPA["lat"]]
        longitudes = [CEDI_TOCANCIPA["lng"]]

        for cli_name in viaje["clientes"]:
            cli = next(c for c in BASE_CLIENTES if c["nombre"] == cli_name)
            latitudes.append(cli["lat"])
            longitudes.append(cli["lng"])

            # Dibujar nodo del cliente
            plt.plot(cli["lng"], cli["lat"], 'o', color=color, markersize=10)
            plt.text(cli["lng"] + 0.003, cli["lat"] + 0.003, f"{cli['nombre']} ({cli['demanda']} kg)", color='white', fontsize=9)
            
        # Cerrar el circuito de regreso al CEDI sin el símbolo '+' erróneo
        latitudes.append(CEDI_TOCANCIPA["lat"])
        longitudes.append(CEDI_TOCANCIPA["lng"])
        
        # Dibujar trazado del camión
        plt.plot(longitudes, latitudes, color=color, linestyle='--', linewidth=2.5, label=f"Ruta Camión {viaje['id_camion'] + 1}")
        
    plt.title("Sabor Sabanero S.A.S. - Rutas Optimizadas de Reparto", fontsize=12, fontweight='bold', pad=15)
    plt.xlabel("Longitud (X)")
    plt.ylabel("Latitud (Y)")
    plt.grid(True, color='#1e293b', linestyle=':')
    plt.legend(loc='best')
    plt.tight_layout()
    print("\n 🎨  Mostrando plano geográfico en ventana emergente...")
    plt.show()

# --- 7. FLUJO DE EJECUCIÓN ---
if __name__ == "__main__":
    # Parámetros de simulación por defecto (pueden ser modificados dinámicamente)
    configuracion_simulacion = {
        "hora_salida": "05:30",
        "temp_ambiente": 15.0,     # °C de la Sabana de Bogotá en horas de la mañana
        "temp_inicial": 2.0,       # Temp. inicial de furgón refrigerado al salir
        "coef_aislamiento": 0.08,  # k_aislamiento estándar
        "perdida_puerta": 0.6      # Pérdida media por apertura de compuerta
    }
    
    print("Verificando viabilidad de la flota...")
    if verificar_viabilidad_flota(BASE_CLIENTES, TRUCK_CAPACITY, MAX_TRUCKS):
        print("Calculando asignación de rutas mínimas (VRP + TSP)...")

        # 1. Resolver el problema de ruteo de vehículos con restricciones de peso
        sub_rutas_agrupadas = resolver_vrp(BASE_CLIENTES, TRUCK_CAPACITY)

        # 2. Simular cada ruta y recolectar estadísticas térmicas y temporales
        viajes_simulados = []
        for i, sub_ruta in enumerate(sub_rutas_agrupadas):
            viajes_simulados.append(simular_ruta_vehiculo(sub_ruta, i, configuracion_simulacion))
            
        # 3. Presentación de Resultados en consola
        imprimir_reporte_flota(viajes_simulados)
        
        # 4. Graficar opcionalmente
        graficar_rutas_sabanera(viajes_simulados)

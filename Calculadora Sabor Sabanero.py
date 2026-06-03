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
CEDI_TOCANCIPA = {
    "id": "tocancipa",
    "nombre": "CEDI Tocancipá",
    "lat": 4.964,
    "lng": -73.912,
    "demanda": 0,
    "descarga": 0,
    "color": "Green"
}

BASE_CLIENTES = [
    {"id": "chia", "nombre": "Chía", "lat": 4.863, "lng": -74.053, "demanda": 1100, "descarga": 25},
    {"id": "cajica", "nombre": "Cajicá", "lat": 4.918, "lng": -74.029, "demanda": 750, "descarga": 15},
    {"id": "zipaquira", "nombre": "Zipaquirá", "lat": 4.996, "lng": -74.003, "demanda": 1400, "descarga": 30},
    {"id": "sopo", "nombre": "Sopó", "lat": 4.908, "lng": -73.938, "demanda": 900, "descarga": 15},
    {"id": "briceno", "nombre": "Briceño", "lat": 4.945, "lng": -73.921, "demanda": 500, "descarga": 10}
]

TRUCK_CAPACITY = 2200          
MAX_TRUCKS = 3                
SCALE_FACTOR_KM_DEGREE = 111.0 
VELOCIDAD_PROMEDIO_KMH = 45.0  

# --- 2. UTILIDADES DE CÁLCULO ---
def calcular_distancia_km(p1, p2):
    dy = p1["lat"] - p2["lat"]
    dx = p1["lng"] - p2["lng"]
    return math.sqrt(dx**2 + dy**2) * SCALE_FACTOR_KM_DEGREE

def convertir_hora_a_minutos(hora_str):
    t = datetime.strptime(hora_str, "%H:%M")
    return t.hour * 60 + t.minute

def convertir_minutos_a_hora(minutos):
    # CORREGIDO: Se cambió 'minutes_mod' por 'minutos_mod'
    minutos_mod = int(minutos % 1440)
    horas = minutos_mod // 60
    mins = minutos_mod % 60
    return f"{horas:02d}:{mins:02d}"

# --- 3. ALGORITMOS DE OPTIMIZACIÓN (VRP & TSP) ---
def verificar_viabilidad_flota(clientes, capacidad_max, max_camiones):
    demanda_total = sum(c["demanda"] for c in clientes)
    capacidad_total = capacidad_max * max_camiones
    if demanda_total > capacidad_total:
        print(f"\n⚠️  ALERTA CRÍTICA: La demanda total ({demanda_total} kg) excede la capacidad total de la flota ({capacidad_total} kg).")
        return False
    return True

def resolver_vrp(clientes, capacidad_max):
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

    rutas_optimizadas = []
    for r in rutas:
        rutas_optimizadas.append(optimizar_tsp_local(r))

    return rutas_optimizadas

def optimizar_tsp_local(sub_ruta):
    if len(sub_ruta) <= 1:
        return sub_ruta
    mejor_secuencia = list(sub_ruta)
    menor_distancia = float("inf")
    
    for perm in itertools.permutations(sub_ruta):
        distancia_actual = calcular_distancia_circuito(perm)
        if distancia_actual < menor_distancia:
            menor_distancia = distancia_actual
            mejor_secuencia = list(perm)
    return mejor_secuencia

def calcular_distancia_circuito(secuencia):
    distancia = 0
    actual = CEDI_TOCANCIPA
    for cliente in secuencia:
        distancia += calcular_distancia_km(actual, cliente)
        actual = cliente
    distancia += calcular_distancia_km(actual, CEDI_TOCANCIPA)
    return distancia

# --- 4. SIMULACIÓN TERMODINÁMICA DE CADENA DE FRÍO ---
def simular_ruta_vehiculo(clientes_sub_ruta, id_camion, config):
    hora_salida_min = convertir_hora_a_minutos(config["hora_salida"])
    temp_ambiente = config["temp_ambiente"]
    temp_inicial = config["temp_inicial"]
    k_aislamiento = config["coef_aislamiento"]
    perdida_puerta = config["perdida_puerta"]
    
    tiempo_actual_min = hora_salida_min
    temp_furgon = temp_inicial
    distancia_acumulada = 0.0
    itinerario = []
    
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
        dist = calcular_distancia_km(actual_nodo, cliente)
        distancia_acumulada += dist
        tiempo_viaje_min = round((dist / VELOCIDAD_PROMEDIO_KMH) * 60)
        
        horas_viaje = tiempo_viaje_min / 60.0
        temp_furgon = temp_ambiente - (temp_ambiente - temp_furgon) * math.exp(-k_aislamiento * hours_viaje if 'hours_viaje' in locals() else -k_aislamiento * horas_viaje)
        tiempo_actual_min += tiempo_viaje_min
        
        temp_furgon += perdida_puerta

        horas_descarga = cliente["descarga"] / 60.0
        k_puerta_abierta = k_aislamiento * 3.5  
        temp_furgon = temp_ambiente - (temp_ambiente - temp_furgon) * math.exp(-k_puerta_abierta * horas_descarga)
        temp_furgon = round(temp_furgon, 1)
        
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
        
    dist_retorno = calcular_distancia_km(actual_nodo, CEDI_TOCANCIPA)
    distancia_acumulada += dist_retorno
    tiempo_retorno_min = round((dist_retorno / VELOCIDAD_PROMEDIO_KMH) * 60)
    
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
def imprimir_reporte_flota(asignaciones, capacidad_usada):
    print("=" * 85)
    print("                SABOR SABANERO S.A.S. - REPORTE DE RUTAS Y CADENA DE FRÍO")
    print("=" * 85)

    total_distancia = 0.0
    total_carga = 0
    camiones_activos = len(asignaciones)
    
    for viaje in asignaciones:
        total_distancia += viaje["distancia_total"]
        total_carga += viaje["carga_total"]

        horas_viaje = viaje["tiempo_total_min"] // 60
        mins_viaje = viaje["tiempo_total_min"] % 60
        print(f"\n 🚚  CAMIÓN 0{viaje['id_camion'] + 1} | Clientes: {'  ➔  '.join(viaje['clientes'])}")
        print(f"   • Carga Útil: {viaje['carga_total']} kg / {capacidad_usada} kg")
        print(f"   • Recorrido: {viaje['distancia_total']} km")
        print(f"   • Duración Estimada: {horas_viaje} h {mins_viaje} min")
        print(f"   • Temp. Retorno CEDI: {viaje['temp_final']} °C")
        print("-" * 85)

        print(f"   {'Punto / Destino':<20} | {'Llegada':<8} | {'Operación / Acción':<24} | {'Parada':<7} | {'Temp. Furgón':<12}")
        print(f"   {'-'*20}-+-{'-'*8}-+-{'-'*24}-+-{'-'*7}-+-{'-'*12}")

        for p in viaje["itinerario"]:
            duracion_str = f"{p['duracion_accion']} min" if p["duracion_accion"] > 0 else "--"
            temp_str = f"{p['temp_furgon']} °C ({p['estado']})"
            print(f"   {p['punto']:<20} | {p['llegada']:<8} | {p['accion']:<24} | {duracion_str:<7} | {temp_str:<12}")
        print("=" * 85)
        
    print("\n 📊  RESUMEN GENERAL DE LA FLOTA:")
    print(f"   • Camiones Utilizados : {camiones_activos} de {MAX_TRUCKS} disponibles")
    print(f"   • Carga Total Entregada: {total_carga} kg")
    print(f"   • Recorrido Total Flota: {total_distancia:.1f} km")
    print("=" * 85)

# --- 6. VISUALIZACIÓN GEOGRÁFICA (OPCIONAL) ---
def graficar_rutas_sabanera(asignaciones):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n 💡  Nota: Para visualizar el plano geográfico interactivo de la Sabana de Bogotá,")
        print("          instale matplotlib ejecutando: 'pip install matplotlib'")
        return
        
    plt.figure(figsize=(9, 7))
    plt.style.use('dark_background')

    plt.plot(CEDI_TOCANCIPA["lng"], CEDI_TOCANCIPA["lat"], 'gH', markersize=14, label="CEDI Tocancipá (Base)")
    plt.text(CEDI_TOCANCIPA["lng"] + 0.003, CEDI_TOCANCIPA["lat"] + 0.003, "CEDI Tocancipá", color='lightgreen', fontweight='bold')
    
    colores_camion = ['#38bdf8', '#c084fc', '#facc15']
    
    for idx, viaje in enumerate(asignaciones):
        color = colores_camion[idx % len(colores_camion)]
        latitudes = [CEDI_TOCANCIPA["lat"]]
        longitudes = [CEDI_TOCANCIPA["lng"]]

        for cli_name in viaje["clientes"]:
            cli = next(c for c in BASE_CLIENTES if c["nombre"] == cli_name)
            latitudes.append(cli["lat"])
            longitudes.append(cli["lng"])
            plt.plot(cli["lng"], cli["lat"], 'o', color=color, markersize=10)
            plt.text(cli["lng"] + 0.003, cli["lat"] + 0.003, f"{cli['nombre']} ({cli['demanda']} kg)", color='white', fontsize=9)
            
        latitudes.append(CEDI_TOCANCIPA["lat"])
        longitudes.append(CEDI_TOCANCIPA["lng"])
        plt.plot(longitudes, latitudes, color=color, linestyle='--', linewidth=2.5, label=f"Ruta Camión {viaje['id_camion'] + 1}")
        
    plt.title("Sabor Sabanero S.A.S. - Rutas Optimizadas de Reparto", fontsize=12, fontweight='bold', pad=15)
    plt.xlabel("Longitud (X)")
    plt.ylabel("Latitud (Y)")
    plt.grid(True, color='#1e293b', linestyle=':')
    plt.legend(loc='best')
    plt.tight_layout()
    print("\n 🎨  Mostrando plano geográfico en ventana emergente...")
    plt.show()

# --- 7. FLUJO DE EJECUCIÓN ---
if __name__ == "__main__":
    configuracion_simulacion = {
        "hora_salida": "05:30",
        "temp_ambiente": 15.0,     
        "temp_inicial": 2.0,       
        "coef_aislamiento": 0.08,  
        "perdida_puerta": 0.6      
    }
    
    print("=" * 60)
    print(" CONFIGURACIÓN DE CAPACIDAD DE LA FLOTA")
    print("=" * 60)
    
    while True:
        try:
            entrada_peso = input(f"Ingrese la capacidad máxima por vehículo en kg [Por defecto {TRUCK_CAPACITY} kg]: ").strip()
            if entrada_peso == "":
                break
            peso_usuario = int(entrada_peso)
            if peso_usuario > 0:
                TRUCK_CAPACITY = peso_usuario
                break
            else:
                print("⚠️ El peso debe ser un número entero mayor a 0.")
        except ValueError:
            print("⚠️ Entrada inválida. Por favor, ingrese solo números enteros.")

    print(f"\n🚀 Iniciando simulación con Capacidad Máxima: {TRUCK_CAPACITY} kg\n")
    
    if verificar_viabilidad_flota(BASE_CLIENTES, TRUCK_CAPACITY, MAX_TRUCKS):
        print("Calculando asignación de rutas mínimas (VRP + TSP)...")
        sub_rutas_agrupadas = resolver_vrp(BASE_CLIENTES, TRUCK_CAPACITY)

        viajes_simulados = []
        for i, sub_ruta in enumerate(sub_rutas_agrupadas):
            viajes_simulados.append(simular_ruta_vehiculo(sub_ruta, i, configuracion_simulacion))
            
        imprimir_reporte_flota(viajes_simulados, TRUCK_CAPACITY)
        graficar_rutas_sabanera(viajes_simulados)

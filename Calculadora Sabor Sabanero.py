import math
import itertools
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA STREAMLIT ---
st.set_page_config(page_title="Sabor Sabanero - Optimización", layout="wide")

st.title("🚛 Sabor Sabanero S.A.S.")
st.subheader("Sistema de Optimización de Flotas y Cadena de Frío (Sabana de Bogotá)")

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
    minutos_mod = int(minutos % 1440)
    horas = minutos_mod // 60
    mins = minutos_mod % 60
    return f"{horas:02d}:{mins:02d}"

# --- 3. ALGORITMOS DE OPTIMIZACIÓN (VRP & TSP) ---
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
    
    # CORREGIDO: Se cambió 'en' por 'in' para evitar el SyntaxError
    for perm in itertools.permutations(sub_ruta):
        distancia_actual = calcular_distancia_circuito(perm)
        if distancia_actual < menor_distancia:
            menor_distancia = distancia_actual
            mejor_secuencia = list(perm)
    return mejor_secuencia

def calcular_distancia_circuito(secuencia):
    dist = 0
    actual = CEDI_TOCANCIPA
    for cliente in secuencia:
        dist += calcular_distancia_km(actual, cliente)
        actual = cliente
    dist += calcular_distancia_km(actual, CEDI_TOCANCIPA)
    return dist

# --- 4. SIMULACIÓN TERMODINÁMICA ---
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
         "Punto": CEDI_TOCANCIPA["nombre"],
         "Llegada": convertir_minutos_a_hora(tiempo_actual_min),
         "Dist. Tramo (km)": 0.0,
         "Dist. Total (km)": 0.0,
         "Acción": "Despacho y Carga",
         "Duración": "0 min",
         "Temp. Furgón": f"{temp_furgon} °C",
         "Estado": "Óptimo"
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
        
        if temp_furgon > 6.0: estado = "🔴 CRÍTICO"
        elif temp_furgon > 4.0: estado = "🟡 ADVERTENCIA"
        else: estado = "🟢 ÓPTIMO"
        
        itinerario.append({
             "Punto": cliente["nombre"],
             "Llegada": convertir_minutos_a_hora(tiempo_actual_min),
             "Dist. Tramo (km)": round(dist, 1),
             "Dist. Total (km)": round(distancia_acumulada, 1),
             "Acción": f"Entrega: {cliente['demanda']} kg",
             "Duración": f"{cliente['descarga']} min",
             "Temp. Furgón": f"{temp_furgon} °C",
             "Estado": estado
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
    
    if temp_furgon > 6.0: estado = "🔴 CRÍTICO"
    elif temp_furgon > 4.0: estado = "🟡 ADVERTENCIA"
    else: estado = "🟢 ÓPTIMO"
    
    itinerario.append({
         "Punto": CEDI_TOCANCIPA["nombre"],
         "Llegada": convertir_minutos_a_hora(tiempo_actual_min),
         "Dist. Tramo (km)": round(dist_retorno, 1),
         "Dist. Total (km)": round(distancia_acumulada, 1),
         "Acción": "Cierre de Ruta",
         "Duración": "--",
         "Temp. Furgón": f"{temp_furgon} °C",
         "Estado": estado
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

# --- INTERFAZ DE CONFIGURACIÓN (BARRA LATERAL) ---
st.sidebar.header("⚙️ Parámetros de Simulación")
h_salida = st.sidebar.text_input("Hora de Salida (HH:MM)", "05:30")
t_amb = st.sidebar.number_input("Temp. Ambiente (°C)", value=15.0)
t_ini = st.sidebar.number_input("Temp. Inicial Furgón (°C)", value=2.0)
c_ais = st.sidebar.slider("Coeficiente Aislamiento", 0.01, 0.20, 0.08)
p_pue = st.sidebar.slider("Pérdida por Apertura Real (°C)", 0.1, 2.0, 0.6)

configuracion_simulacion = {
    "hora_salida": h_salida,
    "temp_ambiente": t_amb,
    "temp_inicial": t_ini,
    "coef_aislamiento": c_ais,
    "perdida_puerta": p_pue
}

# --- PROCESAMIENTO ---
sub_rutas_agrupadas = resolver_vrp(BASE_CLIENTES, TRUCK_CAPACITY)
viajes_simulados = []
for i, sub_ruta in enumerate(sub_rutas_agrupadas):
    viajes_simulados.append(simular_ruta_vehiculo(sub_ruta, i + 1, configuracion_simulacion))

# --- MOSTRAR RESULTADOS EN STREAMLIT ---
col1, col2, col3 = st.columns(3)
total_dist = sum(v["distancia_total"] for v in viajes_simulados)
total_carga = sum(v["carga_total"] for v in viajes_simulados)

col1.metric("🚚 Camiones Activos", f"{len(viajes_simulados)} / {MAX_TRUCKS}")
col2.metric("📦 Carga Total Entregada", f"{total_carga} kg")
col3.metric("🛣️ Recorrido Total Flota", f"{total_dist:.1f} km")

st.markdown("---")

for v in viajes_simulados:
    with st.expander(f"🚛 CAMIÓN 0{v['id_camion']} | Clientes: {' ➔ '.join(v['clientes'])}", expanded=True):
        st.write(f"**Carga Útil:** {v['carga_total']} kg / {TRUCK_CAPACITY} kg | **Recorrido:** {v['distancia_total']} km | **Temp. Retorno:** {v['temp_final']} °C")
        df_itinerario = pd.DataFrame(v["itinerario"])
        st.dataframe(df_itinerario, use_container_width=True)

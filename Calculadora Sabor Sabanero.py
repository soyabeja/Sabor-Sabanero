#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sabor Sabanero S.A.S. - Sistema de Optimización de Flotas y Cadena de Frío
Adaptado para Streamlit
"""
import math
import itertools
from datetime import datetime
import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN GEOGRÁFICA ---
CEDI_TOCANCIPA = {
    "id": "tocancipa", "nombre": "CEDI Tocancipá",
    "lat": 4.964, "lng": -73.912, "demanda": 0, "descarga": 0
}

BASE_CLIENTES = [
    {"id": "chia",      "nombre": "Chía",      "lat": 4.863, "lng": -74.053, "demanda": 1100, "descarga": 25},
    {"id": "cajica",    "nombre": "Cajicá",    "lat": 4.918, "lng": -74.029, "demanda": 750,  "descarga": 15},
    {"id": "zipaquira", "nombre": "Zipaquirá", "lat": 4.996, "lng": -74.003, "demanda": 1400, "descarga": 30},
    {"id": "sopo",      "nombre": "Sopó",      "lat": 4.908, "lng": -73.938, "demanda": 900,  "descarga": 15},
    {"id": "briceno",   "nombre": "Briceño",   "lat": 4.945, "lng": -73.921, "demanda": 500,  "descarga": 10},
]

SCALE_FACTOR_KM_DEGREE = 111.0

# --- 2. UTILIDADES ---
def calcular_distancia_km(p1, p2):
    dy = p1["lat"] - p2["lat"]
    dx = p1["lng"] - p2["lng"]
    return math.sqrt(dx**2 + dy**2) * SCALE_FACTOR_KM_DEGREE

def convertir_hora_a_minutos(hora_str):
    t = datetime.strptime(hora_str, "%H:%M")
    return t.hour * 60 + t.minute

def convertir_minutos_a_hora(minutos):
    minutos_mod = int(minutos % 1440)
    return f"{minutos_mod // 60:02d}:{minutos_mod % 60:02d}"

# --- 3. VRP & TSP ---
def resolver_vrp(clientes, capacidad_max):
    clientes_ordenados = sorted(clientes, key=lambda c: c["demanda"], reverse=True)
    rutas = []
    for cliente in clientes_ordenados:
        asignado = False
        for r in rutas:
            if sum(c["demanda"] for c in r) + cliente["demanda"] <= capacidad_max:
                r.append(cliente)
                asignado = True
                break
        if not asignado:
            rutas.append([cliente])
    return [optimizar_tsp_local(r) for r in rutas]

def optimizar_tsp_local(sub_ruta):
    if len(sub_ruta) <= 1:
        return sub_ruta
    mejor, menor = list(sub_ruta), float("inf")
    for perm in itertools.permutations(sub_ruta):
        d = calcular_distancia_circuito(perm)
        if d < menor:
            menor, mejor = d, list(perm)
    return mejor

def calcular_distancia_circuito(secuencia):
    distancia, actual = 0, CEDI_TOCANCIPA
    for cliente in secuencia:
        distancia += calcular_distancia_km(actual, cliente)
        actual = cliente
    return distancia + calcular_distancia_km(actual, CEDI_TOCANCIPA)

# --- 4. SIMULACIÓN CADENA DE FRÍO ---
def simular_ruta_vehiculo(clientes_sub_ruta, id_camion, config):
    hora_salida_min = convertir_hora_a_minutos(config["hora_salida"])
    ta = config["temp_ambiente"]
    k  = config["coef_aislamiento"]
    kp = k * 3.5

    tiempo_actual = hora_salida_min
    temp = config["temp_inicial"]
    dist_acum = 0.0
    itinerario = [{
        "Punto": CEDI_TOCANCIPA["nombre"],
        "Llegada": convertir_minutos_a_hora(tiempo_actual),
        "Tramo (km)": 0.0, "Total (km)": 0.0,
        "Acción": "Despacho y Carga",
        "Parada (min)": "--",
        "Temp (°C)": round(temp, 1),
        "Estado": "ÓPTIMO"
    }]

    actual = CEDI_TOCANCIPA
    for cliente in clientes_sub_ruta:
        dist = calcular_distancia_km(actual, cliente)
        dist_acum += dist
        t_viaje = round((dist / config["velocidad"]) * 60)
        temp = ta - (ta - temp) * math.exp(-k * (t_viaje / 60))
        tiempo_actual += t_viaje

        temp += config["perdida_puerta"]
        temp = ta - (ta - temp) * math.exp(-kp * (cliente["descarga"] / 60))
        temp = round(temp, 1)

        estado = "CRÍTICO (>6°C)" if temp > 6 else ("ADVERTENCIA" if temp > 4 else "ÓPTIMO")
        itinerario.append({
            "Punto": cliente["nombre"],
            "Llegada": convertir_minutos_a_hora(tiempo_actual),
            "Tramo (km)": round(dist, 1),
            "Total (km)": round(dist_acum, 1),
            "Acción": f"Entrega {cliente['demanda']} kg",
            "Parada (min)": cliente["descarga"],
            "Temp (°C)": temp,
            "Estado": estado
        })
        tiempo_actual += cliente["descarga"]
        actual = cliente

    dist_ret = calcular_distancia_km(actual, CEDI_TOCANCIPA)
    dist_acum += dist_ret
    t_ret = round((dist_ret / config["velocidad"]) * 60)
    temp = round(ta - (ta - temp) * math.exp(-k * (t_ret / 60)), 1)
    tiempo_actual += t_ret

    itinerario.append({
        "Punto": CEDI_TOCANCIPA["nombre"],
        "Llegada": convertir_minutos_a_hora(tiempo_actual),
        "Tramo (km)": round(dist_ret, 1),
        "Total (km)": round(dist_acum, 1),
        "Acción": "Cierre de Ruta",
        "Parada (min)": "--",
        "Temp (°C)": temp,
        "Estado": "CRÍTICO" if temp > 6 else ("ADVERTENCIA" if temp > 4 else "ÓPTIMO")
    })

    return {
        "id_camion": id_camion,
        "itinerario": itinerario,
        "distancia_total": round(dist_acum, 1),
        "carga_total": sum(c["demanda"] for c in clientes_sub_ruta),
        "tiempo_total_min": tiempo_actual - hora_salida_min,
        "temp_final": temp,
        "clientes": [c["nombre"] for c in clientes_sub_ruta]
    }

# --- 5. APP STREAMLIT ---
def main():
    st.set_page_config(page_title="Sabor Sabanero - Flota", page_icon="🚚", layout="wide")
    st.title("🚚 Sabor Sabanero S.A.S.")
    st.caption("Sistema de Optimización de Flotas y Cadena de Frío — Sabana de Bogotá")

    # --- SIDEBAR: Parámetros ---
    with st.sidebar:
        st.header("⚙️ Parámetros de Flota")
        truck_capacity = st.slider("Capacidad por camión (kg)", 500, 5000, 2200, 50)
        max_trucks     = st.slider("Número de camiones", 1, 6, 3)
        velocidad      = st.slider("Velocidad promedio (km/h)", 20, 90, 45, 5)

        st.header("🌡️ Cadena de Frío")
        hora_salida  = st.time_input("Hora de salida", value=datetime.strptime("05:30", "%H:%M").time())
        temp_amb     = st.slider("Temperatura ambiente (°C)", 5, 25, 15)
        temp_inicial = st.slider("Temp. inicial furgón (°C)", -2, 4, 2)
        coef_k       = st.slider("Coef. aislamiento (k)", 0.02, 0.20, 0.08, 0.01)
        perdida_p    = st.slider("Pérdida por apertura (°C)", 0.1, 2.0, 0.6, 0.1)

        st.header("📦 Demanda por Cliente")
        demandas = {}
        for c in BASE_CLIENTES:
            demandas[c["id"]] = st.number_input(
                f"{c['nombre']} (kg)", min_value=50, max_value=3000,
                value=c["demanda"], step=50, key=c["id"]
            )

        correr = st.button("▶ Calcular Rutas", type="primary", use_container_width=True)

    # --- Aplicar demandas personalizadas ---
    clientes = []
    for c in BASE_CLIENTES:
        cliente = c.copy()
        cliente["demanda"] = demandas[c["id"]]
        clientes.append(cliente)

    demanda_total   = sum(c["demanda"] for c in clientes)
    capacidad_total = truck_capacity * max_trucks

    # --- KPIs superiores ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Demanda total", f"{demanda_total:,} kg")
    col2.metric("Capacidad flota", f"{capacidad_total:,} kg")
    col3.metric("Margen disponible", f"{capacidad_total - demanda_total:,} kg")
    col4.metric("Camiones disponibles", max_trucks)

    if demanda_total > capacidad_total:
        st.error(f"⚠️ La demanda ({demanda_total:,} kg) supera la capacidad de la flota ({capacidad_total:,} kg). Ajusta los parámetros.")
        return

    if not correr:
        st.info("Ajusta los parámetros en el panel izquierdo y presiona **▶ Calcular Rutas**.")
        return

    # --- Ejecutar optimización ---
    config = {
        "hora_salida":    hora_salida.strftime("%H:%M"),
        "temp_ambiente":  float(temp_amb),
        "temp_inicial":   float(temp_inicial),
        "coef_aislamiento": coef_k,
        "perdida_puerta": perdida_p,
        "velocidad":      float(velocidad),
    }

    with st.spinner("Optimizando rutas (VRP + TSP)..."):
        sub_rutas = resolver_vrp(clientes, truck_capacity)
        viajes = [simular_ruta_vehiculo(r, i, config) for i, r in enumerate(sub_rutas)]

    st.success(f"✅ {len(viajes)} rutas calculadas correctamente.")

    # --- Mapa de rutas ---
    st.subheader("🗺️ Mapa de Rutas")
    puntos_mapa = [{"lat": CEDI_TOCANCIPA["lat"], "lon": CEDI_TOCANCIPA["lng"], "nombre": "CEDI Tocancipá"}]
    for c in clientes:
        puntos_mapa.append({"lat": c["lat"], "lon": c["lng"], "nombre": c["nombre"]})
    st.map(pd.DataFrame(puntos_mapa))

    # --- Detalle por camión ---
    st.subheader("📋 Detalle de Rutas")
    colores = ["🔵", "🟣", "🟡", "🟠", "🔴", "🟢"]

    for viaje in viajes:
        hh = viaje["tiempo_total_min"] // 60
        mm = viaje["tiempo_total_min"] % 60
        icono = colores[viaje["id_camion"] % len(colores)]

        with st.expander(
            f"{icono} Camión {viaje['id_camion'] + 1}  |  "
            f"{' → '.join(viaje['clientes'])}  |  "
            f"{viaje['carga_total']:,} kg  |  {viaje['distancia_total']} km  |  {hh}h {mm}min",
            expanded=True
        ):
            df = pd.DataFrame(viaje["itinerario"])

            def colorear_estado(val):
                if "CRÍTICO" in str(val):
                    return "background-color: #fee2e2; color: #991b1b;"
                elif "ADVERTENCIA" in str(val):
                    return "background-color: #fef9c3; color: #854d0e;"
                elif "ÓPTIMO" in str(val):
                    return "background-color: #dcfce7; color: #166534;"
                return ""

            st.dataframe(
                df.style.map(colorear_estado, subset=["Estado"]),
                use_container_width=True, hide_index=True
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("Carga útil", f"{viaje['carga_total']:,} kg / {truck_capacity:,} kg")
            c2.metric("Distancia total", f"{viaje['distancia_total']} km")
            c3.metric("Temp. al retorno", f"{viaje['temp_final']} °C",
                      delta_color="inverse",
                      delta="OK" if viaje["temp_final"] <= 4 else "⚠ Revisar")

    # --- Resumen general ---
    st.subheader("📊 Resumen General")
    resumen = pd.DataFrame([{
        "Camión": f"Camión {v['id_camion'] + 1}",
        "Clientes": " → ".join(v["clientes"]),
        "Carga (kg)": v["carga_total"],
        "Distancia (km)": v["distancia_total"],
        "Duración": f"{v['tiempo_total_min']//60}h {v['tiempo_total_min']%60}min",
        "Temp. retorno (°C)": v["temp_final"]
    } for v in viajes])
    st.dataframe(resumen, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()

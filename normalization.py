import pandas as pd
import json
import numpy as np
from sklearn.preprocessing import MinMaxScaler

# --- CONFIGURACIÓN ---
INPUT_FILE = r'C:\Users\marcl\Documents\GitHub\HackEps-2025\raw_data.json'
OUTPUT_FILE = 'barrios_normalizados.csv'

# Lista de barrios que rompen la estadística (Outliers)
BARRIOS_OUTLIERS = ["Downtown Los Angeles"] 

def cargar_datos(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.DataFrame.from_dict(data, orient='index')
        df.index.name = 'Barrio'
        df.reset_index(inplace=True)
        return df
    except Exception as e:
        print(f"Error cargando JSON: {e}")
        return pd.DataFrame()

def limpiar_datos(df):
    # Unificar Población
    if 'population_census' in df.columns:
        df['population'] = df['population_census']
    elif 'population' not in df.columns:
        df['population'] = 1 
        
    cols_to_numeric = df.columns.drop('Barrio')
    for col in cols_to_numeric:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df.fillna(0, inplace=True)
    return df

# --- FUNCIONES NORMALITZACIÓ INTELIGENTE ---

def get_outlier_mask(df):
    """Crea una máscara booleana: True si el barrio es un outlier (Downtown LA)"""
    return df['Barrio'].isin(BARRIOS_OUTLIERS)

def smart_scaler(data, outlier_mask, use_log=False):
    """
    Normaliza datos ignorando outliers para calcular el rango,
    pero aplicando el rango a todos y recortando el exceso.
    """
    # 1. Preprocesamiento (Logaritmo opcional)
    if use_log:
        # log1p para manejar ceros
        processed_data = np.log1p(data)
    else:
        processed_data = data

    # Convertir a formato matriz para sklearn (N, 1)
    X = processed_data.values.reshape(-1, 1)
    
    scaler = MinMaxScaler()
    
    # 2. FIT (Entrenar): Solo con los barrios NORMALES
    # Si hay outliers identificados, entrenamos solo con los que NO son outliers
    if outlier_mask.any():
        X_clean = X[~outlier_mask]
        scaler.fit(X_clean)
    else:
        scaler.fit(X)
        
    # 3. TRANSFORM (Aplicar): A TODOS los barrios (incluido Downtown)
    X_transformed = scaler.transform(X)
    
    # 4. CLIP: Si Downtown LA saca un 1.5, lo bajamos a 1.0
    # Así aseguramos que el rango siempre sea 0-1
    X_clipped = np.clip(X_transformed, 0, 1)
    
    return X_clipped.flatten()

def ingenieria_de_caracteristicas(df):
    print("Calculant mètriques (Ignorant outliers al fit)...")
    
    pop = df['population'] + 1 
    
    # Detectamos dónde está Downtown LA para ignorarlo en el cálculo de escalas
    mask_outliers = get_outlier_mask(df)
    
    # --- 1. COST DE VIDA ---
    # Aquí no solemos necesitar logaritmos, es lineal
    rent_norm = smart_scaler(df['median_rent'], mask_outliers, use_log=False)
    home_norm = smart_scaler(df['median_home_value'], mask_outliers, use_log=False)
    df['score_coste_vida'] = (rent_norm + home_norm) / 2
    
    # --- 2. EDAD ---
    df['score_edad'] = df['median_age']

    # --- 3. SEGURETAT ---
    crimen_per_capita = df['total_crimes'] / pop
    # Logaritmo activado
    crimen_score = smart_scaler(crimen_per_capita, mask_outliers, use_log=True) 
    safety_perception = smart_scaler(df['safety'], mask_outliers, use_log=False)
    df['score_seguridad'] = (safety_perception * 0.4) + ((1 - crimen_score) * 0.6)

    # --- 4. SANITAT ---
    farmacias = smart_scaler(df['pharmacies'] / pop, mask_outliers, use_log=True)
    hospitales = smart_scaler(df['hospitals'] / pop, mask_outliers, use_log=True)
    df['score_sanidad'] = (farmacias * 0.4) + (hospitales * 0.6)

    # --- 5. EDUCACIÓ ---
    escuelas_univ = df['schools'] + df['universities']
    densidad_edu = smart_scaler(escuelas_univ / pop, mask_outliers, use_log=True)
    # Nivel educativo no suele tener outliers locos, usamos false log
    # df['score_educacion'] = densidad_edu # Versión simplificada solo densidad
    # O si quieres mantener nivel educativo:
    nivel_edu = smart_scaler(df['education_level'], mask_outliers, use_log=False)
    df['score_educacion'] = (densidad_edu * 0.5) + (nivel_edu * 0.5)
    
    # --- 6. ESTIL DE VIDA ---
    bares_clubs = df['bars'] + df['nightclubs']
    df['score_vida_nocturna'] = smart_scaler(bares_clubs / pop, mask_outliers, use_log=True)
    
    oferta_cultural = df['museums'] + df['theatres'] + df['cinemas']
    df['score_cultura'] = smart_scaler(oferta_cultural / pop, mask_outliers, use_log=True)

    # --- 7. BOTIGUES (Shopping) ---
    total_shops = df['shops'] + df['supermarkets'] + df['local_businesses']
    df['score_tiendas'] = smart_scaler(total_shops / pop, mask_outliers, use_log=True)

    # --- 8. HOSTELERIA ---
    raw_hosteleria = df['restaurants'] + df['cafes_google_places']
    df['score_hosteleria'] = smart_scaler(raw_hosteleria / pop, mask_outliers, use_log=True)

    # --- 9. CALMA ---
    # Importante: Usamos los scores YA normalizados, así que no aplicamos scaler de nuevo aquí,
    # simplemente operamos matemáticamente.
    densidad_pob = smart_scaler(df['density'], mask_outliers, use_log=True)
    ruido_nocturno = df['score_vida_nocturna']
    ajetreo_comercial = (df['score_tiendas'] + df['score_hosteleria']) / 2
    
    bullicio = (densidad_pob * 0.4) + (ruido_nocturno * 0.3) + (ajetreo_comercial * 0.3)
    df['score_calma'] = 1 - bullicio
    # Clip manual por seguridad por si la suma da > 1 o < 0
    df['score_calma'] = df['score_calma'].clip(0, 1)

    # --- 10. NATURA (Google Parks / Àrea) ---
    area_estimada = pop / (df['density'] + 0.00001)
    parques_por_area = df['parks_google_places'] / area_estimada
    df['score_naturaleza'] = smart_scaler(parques_por_area, mask_outliers, use_log=True)

    # --- 11. MOVILITAT ---
    # A. Walkability (Inversa Àrea)
    score_area = smart_scaler(area_estimada, mask_outliers, use_log=True)
    df['score_walkability'] = 1 - score_area
    
    # B. Transport Públic
    df['score_transporte'] = smart_scaler(df['public_transport_stops'] / pop, mask_outliers, use_log=True)

    return df

def exportar_final(df):
    cols = ['Barrio'] + [c for c in df.columns if 'score_' in c]
    return df[cols].round(4)

# --- MAIN ---
if __name__ == "__main__":
    print("Processant (v7 - Fix Outlier Downtown LA)...")
    df = cargar_datos(INPUT_FILE)
    if not df.empty:
        df = limpiar_datos(df)
        df = ingenieria_de_caracteristicas(df)
        df_final = exportar_final(df)
        df_final.to_csv(OUTPUT_FILE, index=False)
        
        print(f"✅ Fet! Arxiu guardat: {OUTPUT_FILE}")
        
        # Verificar que Downtown LA existe pero no rompe todo (Debería tener 1.0s pero otros barrios deberían tener valores > 0.01)
        check_cols = ['Barrio', 'score_transporte', 'score_hosteleria']
        print("\n--- Control de Calidad ---")
        print("Downtown LA (Debe ser 1.0 o cercano):")
        print(df_final[df_final['Barrio'] == 'Downtown Los Angeles'][check_cols])
        print("\nUn barrio normal (No debe ser 0.0):")
        # Muestra el segundo barrio para comparar
        if len(df_final) > 1:
            print(df_final.iloc[1:2][check_cols])
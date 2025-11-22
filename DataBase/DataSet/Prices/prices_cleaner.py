import pandas as pd
import os

# === 1. Cargar CSV ===
path = r"C:\Users\marcl\Documents\GitHub\HackEps-2025\DataBase\DataSet\Prices\precios_original.csv"
df = pd.read_csv(path, encoding='utf-8-sig')

# === 2. Filtrar solo Los Angeles ===
df_la = df[df["City"] == "Los Angeles"].copy()

# === 3. Seleccionar solo columnas de 2025 ===
cols_2025 = [col for col in df_la.columns if col.startswith("2025-")]

# === 4. Calcular media total de 2025 por ZIP ===
df_mean = df_la[["RegionName"] + cols_2025].copy()
df_mean["mean_2025"] = df_mean[cols_2025].mean(axis=1)

# Nos quedamos solo con RegionName y la media
df_mean = df_mean[["RegionName", "mean_2025"]]

# === 5. Guardar a CSV ===
output_path = os.path.join(os.path.dirname(path), "precios_LA_2025_mean.csv")
df_mean.to_csv(output_path, index=False)

print("Archivo generado:", output_path)

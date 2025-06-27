import os
from google.cloud import documentai_v1
import sqlite3

# Agregá esta línea con la ruta correcta a tu archivo JSON
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/hernan/.google/credentials/agile-extension-283519-f68d56cde68f.json"


print("Ruta de credenciales:", os.environ["GOOGLE_APPLICATION_CREDENTIALS"])

# Si no hay error, la configuración es correcta
client = documentai_v1.DocumentProcessorServiceClient()
print("¡Conexión exitosa con Document AI!")

conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM pdf_data")
print("Total de facturas procesadas:", cursor.fetchone()[0])
conn.close()
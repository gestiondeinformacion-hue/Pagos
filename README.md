# Análisis de pagos 2026 (Streamlit)

Panel interactivo para ver cómo nos fue en los pagos por entidad, concepto y mes.

## Estructura

```
.
├── app.py
├── requirements.txt
├── data/
│   └── datos_dinamica.csv     # separado por |
└── .streamlit/config.toml
```

## Probar en tu computador

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Desplegar con GitHub + Streamlit Community Cloud

1. Crea un repositorio nuevo en GitHub y sube todo el contenido de esta carpeta
   (si son datos sensibles, hazlo **privado**; Streamlit Cloud también lee repos privados).
2. Entra a https://share.streamlit.io e inicia sesión con GitHub.
3. Clic en **Create app** → elige el repositorio, la rama (`main`) y el archivo principal `app.py`.
4. Clic en **Deploy**. Cada `git push` actualiza la app automáticamente.

## Actualizar los datos

- Reemplaza `data/datos_dinamica.csv` y haz `git push`, o
- usa el botón **Cargar otro CSV** de la barra lateral (no cambia el archivo del repositorio).

Columnas requeridas: `NIT|Entidad|Año|Mes_Num|Mes|Fecha|Concepto|Valor`

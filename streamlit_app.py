"""Análisis de pagos por entidad 2026 - Streamlit.

Lee un CSV separado por "|" con columnas:
NIT|Entidad|Año|Mes_Num|Mes|Fecha|Concepto|Valor
"""
import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Análisis de pagos 2026", page_icon="📊", layout="wide")

DATA_PATH = Path(__file__).parent / "data" / "datos_dinamica.csv"
COLS = ["NIT", "Entidad", "Año", "Mes_Num", "Mes", "Fecha", "Concepto", "Valor"]


# ---------- utilidades ----------
def cop(v: float) -> str:
    """$ 1.234.567 (formato colombiano)."""
    return "$ " + f"{v:,.0f}".replace(",", ".")


def mm(v: float) -> str:
    """Millones de pesos: 1.234 M."""
    return f"{v / 1e6:,.0f} M".replace(",", ".")


def corto(nombre: str, n: int = 32) -> str:
    return nombre if len(nombre) <= n else nombre[: n - 1] + "…"


@st.cache_data
def cargar(contenido: bytes | None) -> pd.DataFrame:
    fuente = io.BytesIO(contenido) if contenido else DATA_PATH
    df = pd.read_csv(fuente, sep="|", encoding="utf-8-sig", dtype={"NIT": str})
    faltan = [c for c in COLS if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en el CSV: {', '.join(faltan)}")
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df["Entidad"] = df["Entidad"].str.strip()
    df["Etiqueta"] = df["Entidad"].map(corto)
    return df.sort_values(["Mes_Num", "Entidad", "Concepto"]).reset_index(drop=True)


def variaciones(d: pd.DataFrame) -> pd.DataFrame:
    """Variación % contra el mes inmediatamente anterior, por entidad y concepto."""
    v = d.sort_values(["Entidad", "Concepto", "Mes_Num"]).copy()
    g = v.groupby(["Entidad", "Concepto"])
    v["Mes_Ant"] = g["Mes_Num"].shift()
    v["Valor_Ant"] = g["Valor"].shift()
    v = v[v["Mes_Num"] - v["Mes_Ant"] == 1]  # solo meses consecutivos
    v["Var_%"] = (v["Valor"] / v["Valor_Ant"] - 1) * 100
    return v


# ---------- carga ----------
st.title("📊 ¿Cómo nos fue en los pagos?")
st.caption("Análisis por entidad, concepto y mes · 2026")

with st.sidebar:
    st.header("Filtros")
    subido = st.file_uploader("Cargar otro CSV (separado por |)", type=["csv", "txt"])
    try:
        df = cargar(subido.getvalue() if subido else None)
    except Exception as e:  # noqa: BLE001
        st.error(f"No pude leer el archivo: {e}")
        st.stop()

    conceptos = st.multiselect("Concepto", sorted(df["Concepto"].unique()), default=sorted(df["Concepto"].unique()))
    entidades = st.multiselect("Entidad", sorted(df["Entidad"].unique()))
    nits = st.multiselect("NIT", sorted(df["NIT"].unique()))
    m_min, m_max = int(df["Mes_Num"].min()), int(df["Mes_Num"].max())
    rango = st.slider("Meses (número)", m_min, m_max, (m_min, m_max)) if m_min < m_max else (m_min, m_max)
    umbral = st.slider("Umbral de alerta de variación (±%)", 10, 100, 25, step=5)
    log = st.checkbox("Escala logarítmica en gráfico por entidad", value=True,
                      help="Las entidades tienen magnitudes muy distintas; la escala log permite compararlas.")

d = df[df["Concepto"].isin(conceptos)]
if entidades:
    d = d[d["Entidad"].isin(entidades)]
if nits:
    d = d[d["NIT"].isin(nits)]
d = d[d["Mes_Num"].between(*rango)]

if d.empty:
    st.warning("No hay registros con esos filtros. Ajusta los filtros de la barra lateral.")
    st.stop()

orden_meses = d.drop_duplicates("Mes_Num").sort_values("Mes_Num")["Mes"].tolist()
tm = d.groupby(["Mes_Num", "Mes"], as_index=False)["Valor"].sum().sort_values("Mes_Num")
total = d["Valor"].sum()
promedio = tm["Valor"].mean()
var = variaciones(d)

# ---------- KPIs ----------
pico = tm.loc[tm["Valor"].idxmax()]
valle = tm.loc[tm["Valor"].idxmin()]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total del período", cop(total))
c2.metric("Promedio mensual", cop(promedio))
c3.metric("Mes más alto", f"{pico['Mes']} · {mm(pico['Valor'])}")
if len(tm) >= 2:
    ult, ant = tm.iloc[-1], tm.iloc[-2]
    c4.metric(f"Último mes ({ult['Mes']}) vs anterior", mm(ult["Valor"]), f"{(ult['Valor'] / ant['Valor'] - 1) * 100:+.1f}%")
else:
    c4.metric("Meses analizados", len(tm))

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Resumen", "Tendencia", "Composición", "Alertas y puntos a tener presente", "Datos"])

# ---------- 1. Resumen ----------
with tab1:
    a, b = st.columns(2)
    with a:
        f = go.Figure(go.Scatter(x=tm["Mes"], y=tm["Valor"], mode="lines+markers+text",
                                 text=[mm(v) for v in tm["Valor"]], textposition="top center",
                                 line=dict(width=3, color="#0e7c6b"), name="Total"))
        f.add_hline(y=promedio, line_dash="dash", line_color="#d9822b",
                    annotation_text=f"Promedio {mm(promedio)}", annotation_position="bottom right")
        f.update_layout(title="Total pagado por mes", yaxis_title="Pesos", xaxis=dict(categoryorder="array", categoryarray=orden_meses),
                        margin=dict(t=50, b=10))
        st.plotly_chart(f)
    with b:
        t = tm.copy()
        t["Var"] = t["Valor"].pct_change() * 100
        t = t.dropna()
        if t.empty:
            st.info("Se necesitan al menos dos meses para calcular la variación.")
        else:
            f = go.Figure(go.Bar(x=t["Mes"], y=t["Var"], text=[f"{v:+.1f}%" for v in t["Var"]], textposition="outside",
                                 marker_color=["#0e7c6b" if v >= 0 else "#c23b6b" for v in t["Var"]]))
            f.update_layout(title="Variación % del total contra el mes anterior", yaxis_title="%",
                            xaxis=dict(categoryorder="array", categoryarray=orden_meses), margin=dict(t=50, b=10))
            st.plotly_chart(f)

    tm["Acumulado"] = tm["Valor"].cumsum()
    f = px.area(tm, x="Mes", y="Acumulado", title="Pagos acumulados en el año", markers=True,
                category_orders={"Mes": orden_meses}, color_discrete_sequence=["#3b6fd4"])
    f.update_layout(margin=dict(t=50, b=10))
    st.plotly_chart(f)

# ---------- 2. Tendencia ----------
with tab2:
    s = d.groupby(["Etiqueta", "Concepto", "Mes_Num", "Mes"], as_index=False)["Valor"].sum().sort_values("Mes_Num")
    s["Serie"] = s["Etiqueta"] + " · " + s["Concepto"]
    f = px.line(s, x="Mes", y="Valor", color="Serie", markers=True, title="Tendencia de pagos por entidad y concepto",
                category_orders={"Mes": orden_meses}, hover_data={"Valor": ":,.0f"})
    if log:
        f.update_yaxes(type="log")
    f.update_layout(legend=dict(orientation="h", y=-0.25), margin=dict(t=50), height=520)
    st.plotly_chart(f)

    p = d.pivot_table(index="Etiqueta", columns="Mes", values="Valor", aggfunc="sum").reindex(columns=orden_meses)
    idx = p.div(p.mean(axis=1), axis=0) * 100
    f = go.Figure(go.Heatmap(z=idx.values, x=idx.columns, y=idx.index, zmid=100, colorscale="RdBu_r",
                             text=idx.round(0).astype("Int64").astype(str).values, texttemplate="%{text}",
                             hovertemplate="%{y}<br>%{x}: %{z:.0f} (100 = promedio de la entidad)<extra></extra>",
                             colorbar=dict(title="Índice")))
    f.update_layout(title="Mapa de calor: cada mes frente al promedio de su entidad (100 = promedio)", margin=dict(t=50), height=400)
    st.plotly_chart(f)
    st.caption("Rojo: mes por encima del promedio de esa entidad. Azul: por debajo. Las celdas vacías son meses sin registro.")

# ---------- 3. Composición ----------
with tab3:
    a, b = st.columns(2)
    with a:
        e = d.groupby(["Etiqueta", "Mes_Num", "Mes"], as_index=False)["Valor"].sum().sort_values("Mes_Num")
        f = px.bar(e, x="Mes", y="Valor", color="Etiqueta", title="Pagos por mes, apilados por entidad",
                   category_orders={"Mes": orden_meses})
        f.update_layout(legend=dict(orientation="h", y=-0.3), margin=dict(t=50))
        st.plotly_chart(f)
    with b:
        pe = d.groupby("Etiqueta")["Valor"].sum().sort_values(ascending=False).reset_index()
        pe["Part"] = pe["Valor"] / pe["Valor"].sum() * 100
        pe["Acum"] = pe["Part"].cumsum()
        f = make_subplots(specs=[[{"secondary_y": True}]])
        f.add_bar(x=pe["Etiqueta"], y=pe["Valor"], name="Valor", marker_color="#0e7c6b",
                  text=[f"{v:.1f}%" for v in pe["Part"]], textposition="outside")
        f.add_scatter(x=pe["Etiqueta"], y=pe["Acum"], name="% acumulado", mode="lines+markers",
                      line=dict(color="#d9822b"), secondary_y=True)
        f.update_yaxes(range=[0, 105], ticksuffix="%", secondary_y=True)
        f.update_layout(title="Concentración (Pareto): quién pesa más en el total", margin=dict(t=50),
                        legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(f)

    c = d.groupby(["Mes_Num", "Mes", "Concepto"], as_index=False)["Valor"].sum().sort_values("Mes_Num")
    f = px.bar(c, x="Mes", y="Valor", color="Concepto", title="Cápita vs Evento por mes",
               category_orders={"Mes": orden_meses}, barmode="stack",
               color_discrete_map={"Cápita": "#d9822b", "Evento": "#0e7c6b"})
    f.update_layout(margin=dict(t=50))
    st.plotly_chart(f)

# ---------- 4. Alertas ----------
with tab4:
    st.subheader("Hallazgos automáticos")
    notas = []

    por_ent = d.groupby("Entidad")["Valor"].sum().sort_values(ascending=False)
    if len(por_ent) > 1:
        notas.append(f"**Concentración:** {corto(por_ent.index[0], 60)} representa {por_ent.iloc[0] / total:.1%} del total"
                     + (f"; las dos primeras entidades suman {por_ent.iloc[:2].sum() / total:.1%}." if len(por_ent) > 2 else "."))

    notas.append(f"**Mes más alto:** {pico['Mes']} ({cop(pico['Valor'])}). **Mes más bajo:** {valle['Mes']} ({cop(valle['Valor'])}). "
                 f"La diferencia es de {cop(pico['Valor'] - valle['Valor'])} ({(pico['Valor'] / valle['Valor'] - 1):.0%}).")

    if len(tm) >= 3:
        ult, previos = tm.iloc[-1], tm.iloc[:-1]["Valor"].mean()
        nota = "por encima" if ult["Valor"] > previos else "por debajo"
        notas.append(f"**Último mes ({ult['Mes']}):** {nota} del promedio de los meses anteriores "
                     f"({cop(previos)}) en {abs(ult['Valor'] / previos - 1):.1%}.")

    n_ent = d.groupby("Mes_Num")["Entidad"].nunique()
    if n_ent.nunique() > 1:
        notas.append("**Comparabilidad:** no todas las entidades tienen registro en todos los meses "
                     f"(entre {n_ent.min()} y {n_ent.max()} por mes), así que parte de las variaciones del total puede venir de entidades que entran o salen.")

    if "Cápita" in d["Concepto"].values:
        ents_c = d.loc[d["Concepto"] == "Cápita", "Entidad"].unique()
        sub = d[d["Entidad"].isin(ents_c)]
        part = sub.loc[sub["Concepto"] == "Cápita", "Valor"].sum() / sub["Valor"].sum()
        cap = d[d["Concepto"] == "Cápita"].groupby("Mes")["Valor"].sum()
        notas.append(f"**Cápita:** pesa {part:.1%} del pago de las entidades que la tienen; su mes más alto fue "
                     f"{cap.idxmax()} ({mm(cap.max())}) y el más bajo {cap.idxmin()} ({mm(cap.min())}). "
                     "Debería ser estable; una variación grande merece revisión.")

    for n in notas:
        st.markdown(f"- {n}")

    st.subheader(f"Saltos de más de ±{umbral}% contra el mes anterior")
    al = var[var["Var_%"].abs() >= umbral].sort_values("Var_%", key=abs, ascending=False)
    if al.empty:
        st.success("Ninguna serie superó el umbral.")
    else:
        t = al[["Etiqueta", "Concepto", "Mes", "Valor_Ant", "Valor", "Var_%"]].rename(
            columns={"Etiqueta": "Entidad", "Valor_Ant": "Mes anterior", "Var_%": "Variación %"})
        st.dataframe(t, hide_index=True, column_config={
            "Mes anterior": st.column_config.NumberColumn(format="$ %d"),
            "Valor": st.column_config.NumberColumn(format="$ %d"),
            "Variación %": st.column_config.NumberColumn(format="%+.1f%%")})

    a, b = st.columns(2)
    with a:
        v = d.groupby(["Etiqueta", "Concepto"])["Valor"].agg(["mean", "std", "count"]).reset_index()
        v = v[v["count"] >= 3]
        v["CV"] = v["std"] / v["mean"] * 100
        if not v.empty:
            v["Serie"] = v["Etiqueta"] + " · " + v["Concepto"]
            v = v.sort_values("CV")
            f = px.bar(v, x="CV", y="Serie", orientation="h", title="Volatilidad: variación del pago mes a mes (CV %)",
                       text=v["CV"].map(lambda x: f"{x:.0f}%"), color_discrete_sequence=["#7a5bc7"])
            f.update_layout(margin=dict(t=50), xaxis_title="Coeficiente de variación (%)", yaxis_title=None)
            st.plotly_chart(f)
            st.caption("Más alto = pagos menos predecibles de un mes a otro. Útil para presupuestar y proyectar flujo de caja.")
    with b:
        esperados = set(d["Mes_Num"].unique())
        mes_nom = d.drop_duplicates("Mes_Num").set_index("Mes_Num")["Mes"].to_dict()
        filas = []
        for ent, g in d.groupby("Entidad"):
            falta = sorted(esperados - set(g["Mes_Num"]))
            if falta:
                filas.append({"Entidad": corto(ent, 45), "Meses sin registro": ", ".join(mes_nom[m] for m in falta)})
        st.markdown("**Meses sin registro por entidad**")
        if filas:
            st.dataframe(pd.DataFrame(filas), hide_index=True)
            st.caption("Confirma si fue un mes sin pagos, un retraso en el reporte o una entidad que aún no operaba.")
        else:
            st.success("Todas las entidades tienen registro en todos los meses.")

    st.subheader("Qué deberíamos tener presente")
    st.markdown(
        """
- **Dependencia de pocos prestadores:** si dos o tres entidades suman la mayor parte del pago, cualquier cambio en ellas mueve todo el total. Vale la pena negociar y hacer seguimiento más cercano a esas.
- **Picos y valles:** revisa si responden a cortes de facturación, pagos acumulados de meses anteriores o glosas, antes de tomarlos como tendencia.
- **Cápita vs Evento:** la cápita es más predecible; el evento depende de la demanda. Presupuesta cada uno con su propia lógica.
- **Meses sin registro:** pueden sesgar los comparativos del total. Confírmalos con quien reporta los datos.
- **Volatilidad alta:** dificulta proyectar el flujo de caja; considera una reserva o un promedio móvil para planear.
- **Alcance de los datos:** el archivo trae un valor por mes, pero no indica si es valor pagado, facturado o causado. Confirma ese criterio antes de sacar conclusiones.
"""
    )

# ---------- 5. Datos ----------
with tab5:
    st.dataframe(d[COLS].sort_values(["NIT", "Mes_Num", "Concepto"]), hide_index=True,
                 column_config={"Valor": st.column_config.NumberColumn(format="$ %d"),
                                "Fecha": st.column_config.DateColumn(format="YYYY-MM-DD"),
                                "Año": st.column_config.NumberColumn(format="%d")})
    st.download_button("Descargar datos filtrados (CSV |)",
                       d[COLS].to_csv(sep="|", index=False, date_format="%Y-%m-%d").encode("utf-8-sig"),
                       file_name="datos_filtrados.csv", mime="text/csv")

import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio

ESTILO_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background-color: #fefcf9;
    padding: 2rem;
    font-family: 'Segoe UI', sans-serif;
    color: #333333;
}

[data-testid="stSidebar"] {
    background-color: #f3f0eb;
    border-right: 2px solid #d8d2ca;
}
[data-testid="stSidebar"] > div {
    padding: 1rem;
}

.stButton > button {
    background-color: #cbe4d2;
    color: #2d3a2f;
    border: 2px solid #a6c4b2;
    border-radius: 10px;
    padding: 0.5rem 1rem;
    font-weight: bold;
    transition: all 0.3s ease-in-out;
}
.stButton > button:hover {
    background-color: #b4d6c1;
    color: #1e2a21;
}

h1, h2, h3 {
    color: #4a4a4a;
}
h1 {
    font-size: 2.2rem;
    border-bottom: 2px solid #d8d2ca;
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
}

.stTabs [data-baseweb="tab"] {
    background-color: #ebe7e1;
    color: #333;
    border-radius: 0.5rem 0.5rem 0 0;
    padding: 0.5rem 1rem;
    margin-right: 0.25rem;
    font-weight: bold;
    border: none;
}
.stTabs [aria-selected="true"] {
    background-color: #d6ccc2;
    color: #111;
}

.stTextInput > div > input {
    background-color: #f9f6f2;
    border: 1px solid #ccc;
    border-radius: 0.5rem;
    padding: 0.5rem;
}

.stSelectbox > div {
    background-color: #f9f6f2;
    border-radius: 0.5rem;
}

.stExpander > details {
    background-color: #f2eee9;
    border: 1px solid #ddd3c7;
    border-radius: 0.5rem;
    padding: 0.5rem;
}

::-webkit-scrollbar {
    width: 10px;
}
::-webkit-scrollbar-track {
    background: #f3f0eb;
}
::-webkit-scrollbar-thumb {
    background-color: #b4d6c1;
    border-radius: 10px;
    border: 2px solid #f3f0eb;
}
</style>
"""

layout_base = go.Layout(
    font=dict(family="Times New Roman", size=12),
    plot_bgcolor='white',
    paper_bgcolor='white',
    colorway=px.colors.qualitative.Pastel,
    margin=dict(l=20, r=20, t=40, b=20),
    xaxis=dict(showgrid=False),
    yaxis=dict(showgrid=False),
    hoverlabel=dict(
        bgcolor="white",
        font_size=12,
        font_family="Times New Roman"
    )
)

template_pastel = go.layout.Template(layout=layout_base)
pio.templates["pastel"] = template_pastel
pio.templates.default = "pastel"

PALETA_PASTEL = px.colors.qualitative.Pastel + px.colors.qualitative.Pastel1 + px.colors.qualitative.Pastel2

def aplicar_layout(fig: go.Figure, titulo: str, tamanho_titulo: int = 16) -> go.Figure:
    fig.update_layout(
        template="pastel",
        title={
            "text": titulo,
            "x": 0.5,
            "xanchor": "center",
            "font_size": tamanho_titulo
        },
        paper_bgcolor="white",   
        plot_bgcolor="white",     
        margin=dict(l=20, r=20, t=50, b=20),
        hovermode="x unified",
        legend=dict(
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#CCC",
            borderwidth=1,
            font=dict(size=10)
        )
    )
    return fig

_px_bar_original = px.bar

def _px_bar_customizado(*args, **kwargs) -> go.Figure:
    fig: go.Figure = _px_bar_original(*args, **kwargs)
    seq = PALETA_PASTEL
    modo_barra = getattr(fig.layout, 'barmode', '') or ''
    barras = [t for t in fig.data if isinstance(t, go.Bar)]
    if modo_barra == 'stack':
        for i, trace in enumerate(barras):
            trace.marker.color = seq[i % len(seq)]
    else:
        if len(barras) == 1:
            trace = barras[0]
            vals = trace.x if getattr(trace, 'orientation', None) != 'h' else trace.y
            if hasattr(vals, 'tolist'):
                vals = vals.tolist()
            trace.marker.color = [seq[i % len(seq)] for i in range(len(vals))]
        else:
            for i, trace in enumerate(barras):
                trace.marker.color = seq[i % len(seq)]
    return fig

def aplicar_patch_plotly():
    px.bar = _px_bar_customizado

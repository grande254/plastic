import json
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE = Path(__file__).parent
DATA = BASE / "data"

st.set_page_config(page_title="Plastic Brand Audit Explorer", page_icon="♻️", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1450px;}
[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.22); padding: 14px 16px; border-radius: 14px;}
.hero {padding: 20px 22px; border-radius: 18px; background: linear-gradient(120deg, rgba(34,139,94,.16), rgba(34,139,94,.04)); border: 1px solid rgba(34,139,94,.24); margin-bottom: 1rem;}
.small-note {font-size:.88rem; opacity:.78;}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    df = pd.read_csv(DATA / "brand_audit_clean.csv")
    cleanup = pd.read_csv(DATA / "monthly_plastic_weight.csv", parse_dates=["Date"])
    with open(DATA / "data_quality_summary.json", encoding="utf-8") as f:
        quality = json.load(f)
    return df, cleanup, quality

df, cleanup, quality = load_data()
df["Total Count"] = pd.to_numeric(df["Total Count"], errors="coerce").fillna(0)

st.markdown('<div class="hero"><h1 style="margin:0">♻️ Plastic Brand Audit Explorer</h1><p style="margin:.45rem 0 0">Interactive analysis of brands, parent companies, materials, packaging layers and cleanup activity.</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Analysis filters")
    use_valid = st.toggle("Valid audit records only", value=True, help="Uses source rows marked Yes in ‘Is Valid?’ and with a positive item count.")
    base = df[(df["Is Valid?"].str.lower()=="yes") & (df["Total Count"]>0)].copy() if use_valid else df[df["Total Count"]>0].copy()

    material_options = sorted(base["Type Material"].dropna().unique().tolist())
    layer_options = sorted(base["Layers"].dropna().unique().tolist())
    product_options = sorted(base["Type Product"].dropna().unique().tolist())
    company_options = sorted(base["Parent Company"].dropna().unique().tolist())

    materials = st.multiselect("Material", material_options)
    layers = st.multiselect("Layers", layer_options)
    products = st.multiselect("Product type", product_options)
    companies = st.multiselect("Parent company", company_options)

    filt = base.copy()
    if materials: filt = filt[filt["Type Material"].isin(materials)]
    if layers: filt = filt[filt["Layers"].isin(layers)]
    if products: filt = filt[filt["Type Product"].isin(products)]
    if companies: filt = filt[filt["Parent Company"].isin(companies)]

    st.divider()
    st.download_button("Download filtered data", data=filt.to_csv(index=False).encode("utf-8"), file_name="plastic_audit_filtered.csv", mime="text/csv", use_container_width=True)

pages = st.tabs(["Overview", "Producer responsibility", "Materials & packaging", "Cleanup", "Data quality"])

with pages[0]:
    total = filt["Total Count"].sum()
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Items audited", f"{total:,.0f}")
    c2.metric("Brands", f"{filt['Brand Name'].nunique():,}")
    c3.metric("Parent companies", f"{filt['Parent Company'].nunique():,}")
    c4.metric("Materials", f"{filt['Type Material'].nunique():,}")
    c5.metric("Cleanup weight", f"{cleanup['Plastic Weight (Kgs)'].sum():,.1f} kg")

    left,right = st.columns(2)
    ranked = filt.copy()
    if exclude_unknown:
        ranked = ranked[~ranked["Parent Company"].str.lower().isin(["unbranded","unidentified / missing"])]
        ranked = ranked[~ranked["Brand Name"].str.lower().str.match(r"^(unknown|unkown|unbranded)")]
    top_brands = ranked.groupby("Brand Name", as_index=False)["Total Count"].sum().nlargest(12,"Total Count").sort_values("Total Count")
    fig=px.bar(top_brands,x="Total Count",y="Brand Name",orientation="h",title="Top brands by audited item count",text_auto='.3s')
    fig.update_layout(yaxis_title=None,xaxis_title="Items",height=500)
    left.plotly_chart(fig,use_container_width=True)

    top_companies = ranked.groupby("Parent Company", as_index=False)["Total Count"].sum().nlargest(12,"Total Count").sort_values("Total Count")
    fig=px.bar(top_companies,x="Total Count",y="Parent Company",orientation="h",title="Top parent companies by audited item count",text_auto='.3s')
    fig.update_layout(yaxis_title=None,xaxis_title="Items",height=500)
    right.plotly_chart(fig,use_container_width=True)

    left,right=st.columns(2)
    mat=filt.groupby("Type Material",as_index=False)["Total Count"].sum().sort_values("Total Count",ascending=False)
    fig=px.pie(mat,names="Type Material",values="Total Count",hole=.5,title="Material composition by item count")
    left.plotly_chart(fig,use_container_width=True)
    lay=filt.groupby("Layers",as_index=False)["Total Count"].sum().sort_values("Total Count",ascending=False)
    fig=px.pie(lay,names="Layers",values="Total Count",hole=.5,title="Packaging layers by item count")
    right.plotly_chart(fig,use_container_width=True)

    st.subheader("Derived item categories")
    cat=filt.groupby("Derived Item Category",as_index=False)["Total Count"].sum().sort_values("Total Count",ascending=False)
    fig=px.bar(cat,x="Derived Item Category",y="Total Count",text_auto='.3s')
    fig.update_layout(xaxis_title=None,yaxis_title="Items")
    st.plotly_chart(fig,use_container_width=True)
    st.caption("Derived categories are keyword-based groupings created for exploration; the original Item Description remains available in the data.")

with pages[1]:
    st.subheader("Concentration of producer responsibility")
    producer=filt.copy()
    if exclude_unknown:
        producer=producer[~producer["Parent Company"].str.lower().isin(["unbranded","unidentified / missing"])]
    comp=producer.groupby("Parent Company",as_index=False)["Total Count"].sum().sort_values("Total Count",ascending=False)
    if len(comp):
        comp["Share %"] = comp["Total Count"] / comp["Total Count"].sum() * 100
        comp["Cumulative %"] = comp["Share %"].cumsum()
        top5=comp.head(5)["Share %"].sum(); top10=comp.head(10)["Share %"].sum()
        c1,c2,c3=st.columns(3)
        c1.metric("Top 5 company share", f"{top5:.1f}%")
        c2.metric("Top 10 company share", f"{top10:.1f}%")
        n80=int((comp["Cumulative %"]<80).sum()+1)
        c3.metric("Companies to reach 80%", f"{n80}")

        shown=comp.head(min(25,len(comp))).copy()
        fig=go.Figure()
        fig.add_bar(x=shown["Parent Company"],y=shown["Total Count"],name="Item count",yaxis="y")
        fig.add_scatter(x=shown["Parent Company"],y=shown["Cumulative %"],name="Cumulative share",yaxis="y2",mode="lines+markers")
        fig.update_layout(title="Pareto view: parent-company concentration",height=570,xaxis_tickangle=-55,
            yaxis=dict(title="Items"), yaxis2=dict(title="Cumulative %",overlaying="y",side="right",range=[0,105]),legend=dict(orientation="h",y=1.08))
        st.plotly_chart(fig,use_container_width=True)

        table=comp.copy(); table["Share %"]=table["Share %"].round(2); table["Cumulative %"]=table["Cumulative %"].round(2)
        st.dataframe(table,use_container_width=True,hide_index=True)

    st.subheader("Explore a parent company")
    company_choices = sorted(producer["Parent Company"].unique().tolist()) if len(producer) else []
    company = st.selectbox("Choose company", company_choices)
    if company:
        d=producer[producer["Parent Company"]==company]
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Items",f"{d['Total Count'].sum():,.0f}")
        c2.metric("Brands",f"{d['Brand Name'].nunique():,}")
        c3.metric("Materials",f"{d['Type Material'].nunique():,}")
        company_share=d['Total Count'].sum()/producer['Total Count'].sum()*100 if producer['Total Count'].sum() else 0
        c4.metric("Share of identifiable producer items",f"{company_share:.1f}%")
        l,r=st.columns(2)
        bd=d.groupby('Brand Name',as_index=False)['Total Count'].sum().sort_values('Total Count',ascending=False)
        l.plotly_chart(px.bar(bd,x='Brand Name',y='Total Count',title='Brands within company'),use_container_width=True)
        md=d.groupby('Type Material',as_index=False)['Total Count'].sum()
        r.plotly_chart(px.pie(md,names='Type Material',values='Total Count',hole=.45,title='Material mix'),use_container_width=True)

with pages[2]:
    st.subheader("Material and packaging profile")
    material_company=filt.copy()
    if exclude_unknown:
        material_company=material_company[~material_company["Parent Company"].str.lower().isin(["unbranded","unidentified / missing"])]
    cross=material_company.pivot_table(index="Parent Company",columns="Type Material",values="Total Count",aggfunc="sum",fill_value=0)
    if not cross.empty:
        topnames=material_company.groupby('Parent Company')['Total Count'].sum().nlargest(20).index
        cross=cross.reindex(topnames).fillna(0)
        fig=px.imshow(cross,aspect='auto',labels=dict(x='Material',y='Parent company',color='Items'),title='Top 20 parent companies × material')
        fig.update_layout(height=650)
        st.plotly_chart(fig,use_container_width=True)

    left,right=st.columns(2)
    mat=filt.groupby('Type Material',as_index=False)['Total Count'].sum().sort_values('Total Count',ascending=False)
    left.plotly_chart(px.bar(mat,x='Type Material',y='Total Count',title='Items by material',text_auto='.3s'),use_container_width=True)
    lay=filt.groupby('Layers',as_index=False)['Total Count'].sum().sort_values('Total Count',ascending=False)
    right.plotly_chart(px.bar(lay,x='Layers',y='Total Count',title='Items by layer type',text_auto='.3s'),use_container_width=True)

    matrix=filt.pivot_table(index='Type Material',columns='Layers',values='Total Count',aggfunc='sum',fill_value=0)
    if not matrix.empty:
        st.plotly_chart(px.imshow(matrix,aspect='auto',text_auto='.3s',title='Material × packaging-layer matrix'),use_container_width=True)

with pages[3]:
    st.subheader("Cleanup activity")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Cleanup events",f"{len(cleanup):,}")
    c2.metric("Plastic collected",f"{cleanup['Plastic Weight (Kgs)'].sum():,.1f} kg")
    c3.metric("Sacks",f"{cleanup['No. of sacks'].sum():,.1f}")
    overall=(cleanup['Plastic Weight (Kgs)'].sum()/cleanup['No. of sacks'].sum()) if cleanup['No. of sacks'].sum() else 0
    c4.metric("Overall kg / sack",f"{overall:.1f}")
    fig=px.bar(cleanup.sort_values('Date'),x='Location',y='Plastic Weight (Kgs)',text_auto='.1f',title='Plastic collected by cleanup event',hover_data=['Date','No. of sacks','Kg per Sack'])
    st.plotly_chart(fig,use_container_width=True)
    fig=px.line(cleanup.sort_values('Date'),x='Date',y='Plastic Weight (Kgs)',markers=True,title='Cleanup weight over recorded events')
    st.plotly_chart(fig,use_container_width=True)
    st.info("There are only three cleanup events in this workbook, and both date and location change. Treat the line as a record of observed events, not evidence of a time trend.")
    st.dataframe(cleanup,use_container_width=True,hide_index=True)

with pages[4]:
    st.subheader("Data quality and interpretation")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Source audit rows",f"{quality['source_rows']:,}")
    c2.metric("Valid positive-count rows",f"{quality['valid_rows']:,}")
    c3.metric("Other / excluded rows",f"{quality['invalid_or_unknown_rows']:,}")
    c4.metric("Rows missing parent company",f"{quality['missing_parent_rows']:,}")
    st.markdown("""
**How the dashboard handles the source data**
- The default view includes rows marked **Yes** in the workbook's `Is Valid?` field and with a positive `Total Count`.
- The manual parent-company correction column takes precedence over the lookup result when present.
- `Derived Item Category` is a dashboard-only keyword grouping. It does not replace the original `Item Description`.
- Product/material/layer codes are shown exactly as provided by the workbook rather than expanded into meanings that are not documented in the source.
- Parent company values such as `Unidentified / missing` are retained instead of being guessed.
""")
    st.warning("Brand-audit counts represent what was observed in the audit. They should not automatically be interpreted as market share, production volume, or total environmental responsibility without an appropriate sampling design.")
    st.subheader("Rows needing attention")
    issues=df[(df['Is Valid?'].str.lower()!='yes') | (df['Parent Company']=='Unidentified / missing') | (df['Total Count']<=0)]
    st.dataframe(issues,use_container_width=True,hide_index=True)

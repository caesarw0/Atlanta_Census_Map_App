import streamlit as st
import branca.colormap as cm
import folium
import pandas as pd
import numpy as np
import geopandas as gpd
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Atlanta Census 2020 Dashboard")

# 1. LOAD DATA (Optimized with Lazy Loading for Level 4)
@st.cache_data
def load_base_data():
    districts = gpd.read_file("data/Atlanta_Council_District.geojson").to_crs(epsg=4326)
    precincts = gpd.read_file("data/Atlanta_Precincts_with_council_ID.geojson").to_crs(epsg=4326)
    blocks = gpd.read_file("data/Atlanta_Blocks_Master_Clean.geojson").to_crs(epsg=4326)
    return districts, precincts, blocks

# Performance: Only load parcels matching the current scope
@st.cache_data
def load_filtered_parcels(council_id=None, precinct_id=None, block_id=None):
    # In production, use 'pyogrio' engine or read from a database for speed
    gdf = gpd.read_file("data/Atlanta_Parcels_Level4.geojson").to_crs(epsg=4326)
    
    if block_id:
        return gdf[gdf['BLOCK_GEOID20'].astype(str) == str(block_id)]
    if precinct_id:
        return gdf[gdf['PRECINCT_UNIQUE_ID'].astype(str) == str(precinct_id)]
    if council_id:
        return gdf[gdf['COUNCIL'].astype(str) == str(council_id)]
    return gdf

try:
    dist_gdf, prec_gdf, block_gdf = load_base_data()
except Exception as e:
    st.error(f"Error loading GeoJSON files: {e}")
    st.stop()

# 2. SESSION STATE
if 'view_level' not in st.session_state:
    st.session_state.view_level = 'District'
if 'sel_dist' not in st.session_state:
    st.session_state.sel_dist = None
if 'sel_prec' not in st.session_state:
    st.session_state.sel_prec = None
if 'sel_block' not in st.session_state:
    st.session_state.sel_block = None

# 3. HEADER & NAVIGATION
st.title("Atlanta Census 2020 Drill-Down Dashboard")
nav_cols = st.columns([1, 1, 1, 1, 3])

with nav_cols[0]:
    if st.button("🏙️ City"):
        st.session_state.view_level = 'District'
        st.session_state.sel_dist = st.session_state.sel_prec = st.session_state.sel_block = None
        st.rerun()

if st.session_state.sel_dist:
    with nav_cols[1]:
        if st.button(f"📂 Dist {st.session_state.sel_dist}"):
            st.session_state.view_level = 'Precinct'
            st.session_state.sel_prec = st.session_state.sel_block = None
            st.rerun()

if st.session_state.sel_prec:
    with nav_cols[2]:
        if st.button(f"📍 Prec {st.session_state.sel_prec.split('_')[-1]}"):
            st.session_state.view_level = 'Block'
            st.session_state.sel_block = None
            st.rerun()

if st.session_state.sel_block:
    with nav_cols[3]:
        st.info(f"🏠 Block {st.session_state.sel_block[-4:]}")

st.divider()

# 4. FILTERING & MAP PARAMETERS
if st.session_state.view_level == 'District':
    display_gdf = dist_gdf
    zoom = 11
    tooltip_fields = ['NAME', 'POP20']
    map_center = [33.749, -84.388]

elif st.session_state.view_level == 'Precinct':
    display_gdf = prec_gdf[prec_gdf['COUNCIL_DISTRICT_ID'].astype(str) == str(st.session_state.sel_dist)]
    zoom = 13
    tooltip_fields = ['PRECINCT_UNIQUE_ID', 'POP20']
    
elif st.session_state.view_level == 'Block':
    display_gdf = block_gdf[block_gdf['PRECINCT_UNIQUE_ID'] == st.session_state.sel_prec]
    zoom = 15
    tooltip_fields = ['GEOID20', 'POP20']

elif st.session_state.view_level == 'Parcel':
    # PRE-FILTERING LEVEL 4: Only load parcels for the specific block
    display_gdf = load_filtered_parcels(block_id=st.session_state.sel_block)
    zoom = 18
    tooltip_fields = ['PSTLADDRESS', 'BLOCK_GEOID20'] # Adjust based on your parcel attributes

# Safety check
if display_gdf.empty:
    st.warning("No data found for this selection.")
    st.stop()

bounds = display_gdf.total_bounds
map_center = [(bounds[1] + bounds[3])/2, (bounds[0] + bounds[2])/2]

# 5. RENDER MAP
m = folium.Map(location=map_center, zoom_start=zoom, tiles='OpenStreetMap', control_scale=True)

# COLORING LOGIC (Level 1-3 use POP20, Level 4 is neutral or Categorical)
if st.session_state.view_level != 'Parcel':
    display_gdf['POP20'] = pd.to_numeric(display_gdf['POP20'], errors='coerce').fillna(0)
    vmin, vmax = float(display_gdf['POP20'].min()), float(display_gdf['POP20'].max())
    if vmin == vmax: vmax += 1
    index_steps = np.unique(np.linspace(vmin, vmax, 6)).tolist()
    colormap = cm.linear.YlOrRd_09.scale(vmin, vmax).to_step(index=index_steps)
    colormap.caption = f"Population ({st.session_state.view_level})"
    colormap.add_to(m)

    def style_func(feature):
        val = feature['properties'].get('POP20', 0)
        return {'fillColor': colormap(val), 'color': 'black', 'weight': 0.5, 'fillOpacity': 0.7}
else:
    # Level 4 Style (Parcel)
    style_func = lambda x: {'fillColor': '#3498db', 'color': 'white', 'weight': 1, 'fillOpacity': 0.5}

folium.GeoJson(
    display_gdf,
    style_function=style_func,
    highlight_function=lambda x: {'fillColor': '#f1c40f', 'fillOpacity': 0.8},
    tooltip=folium.GeoJsonTooltip(fields=tooltip_fields)
).add_to(m)

# 6. LABELS (Optimized)
if st.session_state.view_level != 'Parcel':
    label_map = {'District': 'NAME', 'Precinct': 'DISTRICT', 'Block': 'BLOCKCE20'}
    label_col = label_map[st.session_state.view_level]
    
    for _, row in display_gdf.iterrows():
        if row.geometry:
            loc = [row['INTPTLAT20'], row['INTPTLON20']] if 'INTPTLAT20' in row else [row.geometry.centroid.y, row.geometry.centroid.x]
            folium.Marker(location=loc, icon=folium.DivIcon(html=f"""<div style="font-size: 9pt; font-weight: bold; pointer-events: none; text-shadow: 1px 1px 2px white;">{row[label_col]}</div>""")).add_to(m)

# 7. CAPTURE CLICKS & DATA TABLES
map_output = st_folium(m, width="100%", height=700, key=f"map_{st.session_state.view_level}")

if map_output and map_output.get("last_active_drawing"):
    props = map_output["last_active_drawing"]["properties"]
    
    if st.session_state.view_level == 'District':
        st.session_state.sel_dist = props.get('NAME')
        st.session_state.view_level = 'Precinct'
        st.rerun()
    elif st.session_state.view_level == 'Precinct':
        st.session_state.sel_prec = props.get('PRECINCT_UNIQUE_ID')
        st.session_state.view_level = 'Block'
        st.rerun()
    elif st.session_state.view_level == 'Block':
        st.session_state.sel_block = props.get('GEOID20')
        st.session_state.view_level = 'Parcel'
        st.rerun()

# 8. DATA TABLE (Selection Drill-down)
if st.session_state.view_level in ['Precinct', 'Block', 'Parcel']:
    st.subheader(f"Interactive List View: {st.session_state.view_level}")
    
    # Clean up the table for display
    df_table = display_gdf.drop(columns='geometry')
    
    # Corrected selection_mode with hyphen
    event = st.dataframe(
        df_table, 
        use_container_width=True, 
        on_select="rerun", 
        selection_mode="single-row" 
    )
    
    # Handle Table Selection Drill-down
    if event.selection.rows:
        selected_index = event.selection.rows[0]
        selected_row = display_gdf.iloc[selected_index]
        
        if st.session_state.view_level == 'Precinct':
            st.session_state.sel_prec = selected_row['PRECINCT_UNIQUE_ID']
            st.session_state.view_level = 'Block'
            st.rerun()
            
        elif st.session_state.view_level == 'Block':
            st.session_state.sel_block = selected_row['GEOID20']
            st.session_state.view_level = 'Parcel'
            st.rerun()
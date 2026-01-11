import streamlit as st
import pandas as pd
import folium
import geopandas as gpd
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Atlanta Drill-Down Dashboard")

# 1. LOAD DATA
@st.cache_data
def load_all_data():
    # Level 1: District file (NAME: "2")
    districts = gpd.read_file("data/Atlanta_Council_District.geojson").to_crs(epsg=4326)
    # Level 2: Precinct file (COUNCIL_DISTRICT_ID: "2")
    precincts = gpd.read_file("data/Atlanta_Precincts_with_council_ID.geojson").to_crs(epsg=4326)
    # Level 3: Block file (PRECINCT_UNIQUE_ID: "2_08E")
    blocks = gpd.read_file("data/Atlanta_Blocks_Master_Clean.geojson").to_crs(epsg=4326)
    return districts, precincts, blocks

dist_gdf, prec_gdf, block_gdf = load_all_data()

# 2. SESSION STATE MANAGEMENT
if 'view_level' not in st.session_state:
    st.session_state.view_level = 'District'
if 'sel_dist' not in st.session_state:
    st.session_state.sel_dist = None
if 'sel_prec' not in st.session_state:
    st.session_state.sel_prec = None

# 3. BREADCRUMBS & NAVIGATION
st.title("Atlanta Census Drill-Down")
cols = st.columns(4)
with cols[0]:
    if st.button("🏙️ City View"):
        st.session_state.view_level = 'District'
        st.rerun()
if st.session_state.sel_dist:
    with cols[1]:
        if st.button(f"📂 District {st.session_state.sel_dist}"):
            st.session_state.view_level = 'Precinct'
            st.rerun()
if st.session_state.sel_prec:
    with cols[2]:
        st.write(f"📍 Precinct {st.session_state.sel_prec}")

st.divider()

# 4. FILTERING LOGIC
# 4. FILTERING LOGIC
if st.session_state.view_level == 'District':
    display_gdf = dist_gdf
    zoom = 11
    tooltip_fields = ['NAME']
    # Default center if something goes wrong
    map_center = [33.749, -84.388]

elif st.session_state.view_level == 'Precinct':
    display_gdf = prec_gdf[prec_gdf['COUNCIL_DISTRICT_ID'].astype(str) == str(st.session_state.sel_dist)]
    zoom = 13
    tooltip_fields = ['DISTRICT', 'COUNCIL_DISTRICT_ID', 'PRECINCT_UNIQUE_ID']
    
elif st.session_state.view_level == 'Block':
    # CRITICAL: Strip whitespace and force string for matching
    target_precinct = str(st.session_state.sel_prec).strip()
    # st.write(f"target_precinct: {target_precinct}")
    # st.write(f"block_gdf['PRECINCT_UNIQUE_ID'].astype(str).str.strip(): {block_gdf['PRECINCT_UNIQUE_ID'].astype(str).str.strip().unique()}")
    display_gdf = block_gdf[block_gdf['PRECINCT_UNIQUE_ID'].astype(str).str.strip() == target_precinct]
    zoom = 15
    tooltip_fields = ['GEOID20', 'PRECINCT_UNIQUE_ID']

# --- SAFETY CHECK FOR MAP CENTER ---
if not display_gdf.empty:
    bounds = display_gdf.total_bounds
    # If bounds are valid, calculate center
    map_center = [(bounds[1] + bounds[3])/2, (bounds[0] + bounds[2])/2]
else:
    # If display_gdf is empty, don't crash! 
    # Fallback to the Atlanta center and show a warning
    map_center = [33.749, -84.388]
    st.error(f"⚠️ No blocks found for Precinct ID: '{st.session_state.sel_prec}'")
    st.write("Available IDs in Block file:", block_gdf['PRECINCT_UNIQUE_ID'].unique())

# 5. RENDER MAP
# Calculate center dynamically
bounds = display_gdf.total_bounds
map_center = [(bounds[1] + bounds[3])/2, (bounds[0] + bounds[2])/2]

m = folium.Map(location=map_center, zoom_start=zoom, tiles='OpenStreetMap')

# Add the Layer
if not display_gdf.empty and 'geometry' in display_gdf.columns:
    folium.GeoJson(
        display_gdf,
        style_function=lambda x: {'fillColor': '#3498db', 'color': 'black', 'weight': 1, 'fillOpacity': 0.3},
        highlight_function=lambda x: {'fillColor': '#f1c40f', 'fillOpacity': 0.5},
        tooltip=folium.GeoJsonTooltip(fields=tooltip_fields)
    ).add_to(m)

map_output = st_folium(m, width="100%", height=600, key=f"map_{st.session_state.view_level}")

# 6. CLICK HANDLING (DRILL-DOWN ENGINE)
if map_output and map_output.get("last_active_drawing"):
    props = map_output["last_active_drawing"]["properties"]
    
    if st.session_state.view_level == 'District':
        # Get 'NAME' from Level 1 to filter Level 2
        st.session_state.sel_dist = props.get('NAME')
        st.session_state.view_level = 'Precinct'
        st.rerun()
        
    elif st.session_state.view_level == 'Precinct':
        # Get 'PRECINCT_UNIQUE_ID' from Level 2 to filter Level 3
        st.session_state.sel_prec = props.get('PRECINCT_UNIQUE_ID')
        st.session_state.view_level = 'Block'
        st.rerun()

# 7. DATA TABLE (Only shows at the Block level)
if st.session_state.view_level == 'Block':
    st.subheader(f"Census Block Records for Precinct {st.session_state.sel_prec}")
    # Display table excluding geometry
    st.dataframe(display_gdf.drop(columns='geometry'), use_container_width=True)
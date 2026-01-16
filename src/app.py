import streamlit as st
import branca.colormap as cm
import folium
import pandas as pd
import numpy as np
import geopandas as gpd
from streamlit_folium import st_folium

CENSUS_METRIC_MAPPING = {
    "TSRR001_001": "Internet Self-Response rate at the start of NRFU in the 2020 Census",
    "TSRR001_002": "Paper Self-Response rate at the start of NRFU in the 2020 Census",
    "TSRR001_003": "CQA Self-Response rate at the start of NRFU in the 2020 Census",
    "TSRR001_004": "Total (Internet+Paper+CQA) Self-Response rate at the start of NRFU in the 2020 Census",
    "TSRR001_005": "Final Internet Self-Response rate in the 2020 Census",
    "TSRR001_006": "Final Paper Self-Response rate in the 2020 Census",
    "TSRR001_007": "Final CQA Self-Response rate in the 2020 Census",
    "TSRR001_008": "Final Total (Internet+Paper+CQA) Self-Response rate in the 2020 Census",
    "TSRR001_009": "Internet Return rate at the start of NRFU in the 2020 Census",
    "TSRR001_010": "Paper Return rate at the start of NRFU in the 2020 Census",
    "TSRR001_011": "CQA Return rate at the start of NRFU in the 2020 Census",
    "TSRR001_012": "Total (Internet+Paper+CQA) Return rate at the start of NRFU in the 2020 Census",
    "TSRR001_013": "Final Internet Return rate in the 2020 Census",
    "TSRR001_014": "Final Paper Return rate in the 2020 Census",
    "TSRR001_015": "Final CQA Return rate in the 2020 Census",
    "TSRR001_016": "Final Total (Internet+Paper+CQA) Return rate in the 2020 Census",
    "TSRR001_017": "UAA rate at the start of NRFU in the 2020 Census",
    "TSRR001_018": "Final UAA rate in the 2020 Census",
    "TSRR001_019": "Self-response rate at the NRFU cut date in the 2010 Census",
    "TSRR001_020": "Final Self-Response rate in the 2010 Census",
    "TSRR001_021": "Return rate at the NRFU cut date in the 2010 Census",
    "TSRR001_022": "Final Return rate in the 2010 Census",
    "TSRR001_023": "UAA rate at the NRFU cut date in the 2010 Census",
    "TSRR001_024": "Final UAA rate in the 2010 Census"
}

st.set_page_config(layout="wide", page_title="Atlanta Census 2020 Dashboard")

# 1. LOAD DATA (Optimized with Lazy Loading for Level 4)
@st.cache_data
def load_base_data():
    districts = gpd.read_file("data/Atlanta_Council_Census_Aggregated.geojson").to_crs(epsg=4326)
    precincts = gpd.read_file("data/Atlanta_Precincts_Census_Assigned.geojson").to_crs(epsg=4326)
    blocks = gpd.read_file("data/Atlanta_Blocks_Master_Clean.geojson").to_crs(epsg=4326)
    parcels = gpd.read_file("data/Atlanta_Parcels_Level4.geojson").to_crs(epsg=4326)

    for gdf in [districts, precincts]:
        # 1. Round numeric values
        for col in CENSUS_METRIC_MAPPING.keys():
            if col in gdf.columns:
                gdf[col] = pd.to_numeric(gdf[col], errors='coerce').round(1)
        
        # 2. Rename columns globally
        # We only rename columns that exist in the CENSUS_METRIC_MAPPING
        gdf.rename(columns=CENSUS_METRIC_MAPPING, inplace=True)
    return districts, precincts, blocks, parcels

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
    dist_gdf, prec_gdf, block_gdf, parcels_gdf = load_base_data()
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
census_display_names = list(CENSUS_METRIC_MAPPING.values())
# 4. FILTERING & MAP PARAMETERS
if st.session_state.view_level == 'District':
    display_gdf = dist_gdf
    zoom = 11
    tooltip_fields = ['NAME', 'POP20', CENSUS_METRIC_MAPPING['TSRR001_008']]
    map_center = [33.749, -84.388]

elif st.session_state.view_level == 'Precinct':
    display_gdf = prec_gdf[prec_gdf['COUNCIL_DISTRICT_ID'].astype(str) == str(st.session_state.sel_dist)]
    zoom = 13
    tooltip_fields = ['PRECINCT_UNIQUE_ID', 'POP20', CENSUS_METRIC_MAPPING['TSRR001_008']]
    
elif st.session_state.view_level == 'Block':
    display_gdf = block_gdf[block_gdf['PRECINCT_UNIQUE_ID'] == st.session_state.sel_prec]
    zoom = 15
    tooltip_fields = ['GEOID20', 'POP20']

elif st.session_state.view_level == 'Parcel':
    # PRE-FILTERING LEVEL 4: Only load parcels for the specific block
    display_gdf = parcels_gdf[parcels_gdf['BLOCK_GEOID20'].astype(str) == str(st.session_state.sel_block)]
    zoom = 18
    tooltip_fields = ['PSTLADDRESS'] # Adjust based on your parcel attributes

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

# 8. DATA TABLE (Conditional Columns with Ascending Sort)
if st.session_state.view_level in ['District', 'Precinct', 'Block', 'Parcel']:
    st.subheader(f"Interactive List View: {st.session_state.view_level}")
    target_sort_name = CENSUS_METRIC_MAPPING['TSRR001_008']
    # 1. Setup Column Logic and Rename Dictionary
    if st.session_state.view_level == 'District':
        cols_to_show = ['NAME'] + census_display_names
        sort_col = target_sort_name
        rename_dict = {
            'NAME': 'Council District',
            **CENSUS_METRIC_MAPPING
        }
    
    elif st.session_state.view_level == 'Precinct':
        cols_to_show = ['PRECINCT_UNIQUE_ID', 'POP20'] + census_display_names
        sort_col = target_sort_name
        rename_dict = {
            'POP20': 'Population',
            **CENSUS_METRIC_MAPPING
        }
    
    elif st.session_state.view_level == 'Block':
        cols_to_show = ['GEOID20', 'POP20']
        sort_col = 'POP20' # Sort blocks by population instead
        rename_dict = {'POP20': 'Population'}
        
    else: # Parcel / Level 4
        cols_to_show = ['PSTLADDRESS', 'BLOCK_GEOID20']
        sort_col = 'PSTLADDRESS'
        rename_dict = {'PSTLADDRESS': 'Property Address', 'BLOCK_GEOID20': 'Parent Block ID'}

    # 2. Filter, Sort, and Rename
    df_visible = display_gdf[cols_to_show].copy()
    
    # Sort while columns still have original names
    df_visible = df_visible.sort_values(by=sort_col, ascending=True)

    # 3. Render Table with Hidden Technical Columns
    is_level_4 = (st.session_state.view_level == 'Parcel')
    mode = "single-row" if not is_level_4 else None
    
    # We use st.dataframe's column_config to rename columns for display 
    # without actually changing the underlying dataframe column names.
    event = st.dataframe(
        df_visible, 
        use_container_width=True, 
        on_select="rerun" if not is_level_4 else "ignore",
        selection_mode=mode,
        hide_index=True,
        column_config={
            "NAME": "Council District",
            # "PRECINCT_UNIQUE_ID": "Precinct ID",
            "GEOID20": "Block Group ID",
            "POP20": "Population",
            "TOTAL_POP20": "Total Population",
            "PSTLADDRESS": "Address",
            "BLOCK_GEOID20": "Parent Block"
        }
    )

    # 4. Drill-Down Logic (Now works because names are stable)
    if mode == "single-row" and event.selection.rows:
        selected_row_index = event.selection.rows[0]
        
        # Get the technical data from the visible dataframe
        # df_visible still has columns like 'PRECINCT_UNIQUE_ID'
        selected_row = df_visible.iloc[selected_row_index]
        
        if st.session_state.view_level == 'District':
            st.session_state.sel_dist = selected_row['NAME']
            st.session_state.view_level = 'Precinct'
            st.rerun()
            
        elif st.session_state.view_level == 'Precinct':
            st.session_state.sel_prec = selected_row['PRECINCT_UNIQUE_ID']
            st.session_state.view_level = 'Block'
            st.rerun()
            
        elif st.session_state.view_level == 'Block':
            st.session_state.sel_block = selected_row['GEOID20']
            st.session_state.view_level = 'Parcel'
            st.rerun()
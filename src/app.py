import streamlit as st
import branca.colormap as cm
import folium
import pandas as pd
import numpy as np
import geopandas as gpd
from streamlit_folium import st_folium

st.set_page_config(layout="wide", page_title="Atlanta Census 2020 Dashboard")

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

try:
    dist_gdf, prec_gdf, block_gdf = load_all_data()
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

# 3. HEADER & NAVIGATION
st.title("Atlanta Census 2020 Drill-Down Dashboard")
nav_cols = st.columns([2, 2, 2])

with nav_cols[0]:
    if st.button("🏙️ City View"):
        st.session_state.view_level = 'District'
        st.session_state.sel_dist = None
        st.session_state.sel_prec = None
        st.rerun()

if st.session_state.sel_dist:
    with nav_cols[1]:
        if st.button(f"📂 District {st.session_state.sel_dist}"):
            st.session_state.view_level = 'Precinct'
            st.session_state.sel_prec = None
            st.rerun()

if st.session_state.sel_prec:
    with nav_cols[2]:
        st.info(f"📍 Precinct {st.session_state.sel_prec}")

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
    tooltip_fields = ['DISTRICT', 'COUNCIL_DISTRICT_ID', 'PRECINCT_UNIQUE_ID', 'POP20']
    
elif st.session_state.view_level == 'Block':
    target = str(st.session_state.sel_prec).strip()
    display_gdf = block_gdf[block_gdf['PRECINCT_UNIQUE_ID'].astype(str).str.strip() == target]
    zoom = 15
    tooltip_fields = ['GEOID20', 'PRECINCT_UNIQUE_ID', 'HOUSING20', 'POP20']

# Safety check for empty filters (prevents NaN crash)
if not display_gdf.empty:
    bounds = display_gdf.total_bounds
    map_center = [(bounds[1] + bounds[3])/2, (bounds[0] + bounds[2])/2]
else:
    map_center = [33.749, -84.388]
    st.warning("No data found for the selected area. Showing default view.")

# 5. RENDER MAP
m = folium.Map(location=map_center, zoom_start=zoom, tiles='OpenStreetMap', control_scale=True)

if not display_gdf.empty:
    # 1. Force numeric and handle missing data
    display_gdf['POP20'] = pd.to_numeric(display_gdf['POP20'], errors='coerce').fillna(0)
    
    # 2. Get min and max
    vmin = float(display_gdf['POP20'].min())
    vmax = float(display_gdf['POP20'].max())

    # --- SAFETY BUFFER: Handle ZeroDivisionError ---
    # If all values are the same (e.g., 0 or 100), create a dummy range [val, val + 1]
    if vmin == vmax:
        vmax = vmin + 1
    
    # 3. Create Index Steps
    # Use np.unique to ensure we don't have duplicate steps
    index_steps = np.unique(np.linspace(vmin, vmax, 6)).tolist()
    
    # Second safety check: if linspace + unique resulted in only 1 value
    if len(index_steps) < 2:
        index_steps = [vmin, vmax]

    # 4. Build Colormap
    # Start with a fixed range base map to avoid scale conflicts
    base_map = cm.linear.YlOrRd_09.scale(vmin, vmax)
    colormap = base_map.to_step(index=index_steps)
    
    colormap.caption = f'Population ({st.session_state.view_level})'
    colormap.add_to(m)
    
    # 5. Define Style Function with internal safety
    def style_func(feature):
        pop = feature['properties'].get('POP20')
        # Handle None or non-numeric properties safely
        try:
            val = float(pop) if pop is not None else 0.0
        except (ValueError, TypeError):
            val = 0.0
            
        return {
            'fillColor': colormap(val),
            'color': 'black',
            'weight': 1 if st.session_state.view_level != 'Block' else 0.5,
            'fillOpacity': 0.7
        }

    # 6. Add GeoJson
    folium.GeoJson(
        display_gdf,
        style_function=style_func,
        highlight_function=lambda x: {'fillColor': '#f1c40f', 'fillOpacity': 0.5},
        tooltip=folium.GeoJsonTooltip(fields=tooltip_fields)
    ).add_to(m)

    # ADD TEXT LABELS (Keep for District Level)
        
    if st.session_state.view_level == 'District':
        annotation_field = 'NAME'
    elif st.session_state.view_level == 'Precinct':
        annotation_field = 'PRECINCT_I'
    elif st.session_state.view_level == 'Block':
        annotation_field = 'BLOCKCE20'
    for _, row in display_gdf.iterrows():
        if row.geometry:
            # if st.session_state.view_level == 'Block', we use INTPTLAT20 and INTPTLON20
            if st.session_state.view_level == 'Block':
                location = [row['INTPTLAT20'], row['INTPTLON20']]
            else:
                c = row.geometry.centroid
                location = [c.y, c.x]
            folium.Marker(
                location=location,
                icon=folium.DivIcon(
                    icon_size=(100,20),
                    icon_anchor=(50,10),
                    html=f"""<div style="
                            font-size: 10pt; 
                            color: black; 
                            font-weight: bold; 
                            text-align: center; 
                            pointer-events: none; 
                            user-select: none;
                            text-shadow: 2px 2px 0px #fff, -2px -2px 0px #fff, 2px -2px 0px #fff, -2px 2px 0px #fff;">
                            {row[annotation_field] if not pd.isna(row[annotation_field]) else ''}
                            </div>"""
                )
            ).add_to(m)

# 6. CAPTURE CLICKS
map_output = st_folium(
    m, 
    width="100%", 
    height=700, 
    key=f"map_{st.session_state.view_level}", # Unique key per level
    returned_objects=["last_active_drawing"]
)

# 7. CLICK HANDLING (Update State)
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

# 8. DATA TABLE (Bottom Section)
if st.session_state.view_level == 'Block':
    st.subheader(f"Detailed Records: Precinct {st.session_state.sel_prec}")
    if not display_gdf.empty:
        # Create a clean version for the table (no geometry)
        df_table = display_gdf.drop(columns='geometry')
        df_table = df_table[['GEOID20', 'COUNCIL_DISTRICT_ID', 'DISTRICT', 'NAME20', 'HOUSING20', 'POP20']]
        # sort by POP20 ascending
        df_table = df_table.sort_values(by='POP20', ascending=True)
        st.dataframe(df_table, use_container_width=True)
        
        # CSV Download Button
        csv = df_table.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download This Data", csv, "precinct_data.csv", "text/csv")
    else:
        st.info("No records found for this block.")
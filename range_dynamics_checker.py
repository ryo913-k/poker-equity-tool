import streamlit as st
import random
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from treys import Card, Evaluator
from collections import Counter

st.set_page_config(page_title="Poker Equity Tool", layout="wide")

# Treysの評価機 (キャッシュして高速化)
@st.cache_resource
def load_evaluator():
    return Evaluator()

try:
    with st.spinner('Loading poker engine...'):
        evaluator = load_evaluator()
except: st.stop()

# ==========================================
# 0. 設定 & データ管理
# ==========================================
with st.sidebar:
    st.header("🔧 Settings")
    st.markdown("**Simulation Accuracy**")
    sim_iterations = st.slider("Iterations per Hand", 100, 5000, 500, 100)
    st.divider()
    if st.button("Reset App", type="primary"):
        for key in st.session_state.keys(): del st.session_state[key]
        st.rerun()

if 'board_cards' not in st.session_state: st.session_state['board_cards'] = ["Th", "8d", "2c"]
if 'widget_id_counter' not in st.session_state: st.session_state['widget_id_counter'] = 0
if 'hero_range_val' not in st.session_state: st.session_state.hero_range_val = "QQ+, AKs, AKo"
if 'villain_range_val' not in st.session_state: st.session_state.villain_range_val = "TT+, AJs+, KQs, AQo+"

# ==========================================
# ユーティリティ
# ==========================================
HAND_ORDER = [
    "AA", "KK", "QQ", "AKs", "JJ", "AKo", "AQs", "TT", "AJs", "KQs", "99", "ATs", "AQo", "KJs", "88", "QJs", "JTs", 
    "AJo", "KQo", "77", "ATo", "KTs", "QTs", "T9s", "KJo", "QJo", "J9s", "98s", "66", "A9s", "A5s", "A8s", "K9s", "Q9s", "JTo", 
    "55", "A4s", "A7s", "A3s", "T8s", "87s", "A2s", "K8s", "Q8s", "J8s", "44", "A9o", "KTo", "QTo", "97s", "76s", "33", "22", 
    "A6s", "K7s", "Q7s", "J7s", "T7s", "86s", "65s", "A8o", "K9o", "Q9o", "J9o", "T9o", 
    "K6s", "Q6s", "J6s", "T6s", "96s", "75s", "54s", "A5o", "A7o", "K8o", "Q8o", "J8o", "T8o", "98o", "87o", 
    "K5s", "Q5s", "J5s", "T5s", "95s", "85s", "64s", "A4o", "A6o", "K7o", "Q7o", "J7o", "T7o", "97o", "76o", 
    "K4s", "Q4s", "J4s", "T4s", "94s", "84s", "74s", "53s", "A3o", "A2o", "65o", "54o", 
    "K3s", "Q3s", "J3s", "T3s", "93s", "83s", "73s", "63s", "43s", 
    "K2s", "Q2s", "J2s", "T2s", "92s", "82s", "72s", "62s", "52s", "42s", "32s", 
    "K6o", "Q6o", "J6o", "T6o", "96o", "86o", "75o", "64o", "53o", 
    "K5o", "Q5o", "J5o", "T5o", "95o", "85o", "74o", "63o", "52o", "43o", 
    "K4o", "Q4o", "J4o", "T4o", "94o", "84o", "73o", "62o", "42o", "32o", 
    "K3o", "Q3o", "J3o", "T3o", "93o", "83o", "72o", "K2o", "Q2o", "J2o", "T2o", "92o", "82o"
]

def get_range_string_from_percent(start_p, end_p):
    if start_p >= end_p: return ""
    total = 169; s_idx = int(total*(start_p/100)); e_idx = int(total*(end_p/100))
    sel = HAND_ORDER[s_idx:e_idx]
    return ", ".join(sel) if sel else ""

def card_to_str(card_int): return Card.int_to_str(card_int)
def str_to_card(card_str):
    clean = card_str.replace("10", "T").replace("0", "T")
    try: return Card.new(clean)
    except: return None

def parse_range_notation(range_str):
    ranks = '23456789TJQKA'; suits = 'cdhs'; combos = [] 
    if not range_str: return []
    parts = [p.strip() for p in range_str.split(',')]
    for part in parts:
        if len(part) < 2: continue
        part = part.replace("10", "T")
        if len(part) == 4 and part[1] in suits and part[3] in suits:
            try:
                c1 = str_to_card(part[:2]); c2 = str_to_card(part[2:])
                if c1 and c2: combos.append([c1, c2])
                continue
            except: pass
        try:
            r1=part[0]; r2=part[1]; r1i=ranks.find(r1); r2i=ranks.find(r2)
            if r1i==-1 or r2i==-1: continue
            is_plus='+' in part; is_s='s' in part; is_o='o' in part
            if r1i == r2i:
                top = 12 if is_plus else r1i
                for r in range(r1i, top+1):
                    for i in range(4):
                        for j in range(i+1, 4): combos.append([str_to_card(ranks[r]+suits[i]), str_to_card(ranks[r]+suits[j])])
            else:
                if r1i < r2i: r1i, r2i, r1, r2 = r2i, r1i, r2, r1
                top_k = r1i - 1 if is_plus else r2i
                for k in range(r2i, top_k+1):
                    if is_s or (not is_o and not is_s):
                        for s in suits: combos.append([str_to_card(r1+s), str_to_card(ranks[k]+s)])
                    if is_o or (not is_o and not is_s):
                        for s1 in suits:
                            for s2 in suits:
                                if s1!=s2: combos.append([str_to_card(r1+s1), str_to_card(ranks[k]+s2)])
        except: continue
    return combos

def create_range_grid_visual(combo_list):
    rank_map = {r: i for i, r in enumerate("AKQJT98765432")}
    grid_data = [[0]*13 for _ in range(13)]
    for hand in combo_list:
        try:
            c1_str = card_to_str(hand[0]); c2_str = card_to_str(hand[1])
            r1c = c1_str[0].upper(); r2c = c2_str[0].upper()
            s1c = c1_str[1]; s2c = c2_str[1]
            i1 = rank_map.get(r1c); i2 = rank_map.get(r2c)
            if i1 is None or i2 is None: continue
            if i1 < i2: h, l = i1, i2
            else: h, l = i2, i1
            if r1c == r2c: grid_data[h][h] = 1 
            elif s1c == s2c: grid_data[h][l] = 1 
            else: grid_data[l][h] = 1 
        except: continue
    return grid_data

def display_board_streets(cards):
    if not cards:
        st.info("Preflop")
        return
    c_flop, c_turn, c_river = st.columns([3, 1.2, 1.2])
    def get_img_url(card_int):
        c_str = card_to_str(card_int)
        r = c_str[0].upper().replace("T", "0"); s = c_str[1].upper()
        return f"https://deckofcardsapi.com/static/img/{r}{s}.png"
    with c_flop:
        st.markdown("**FLOP**")
        if len(cards) > 0:
            cols = st.columns(3)
            for i, card in enumerate(cards[:3]):
                with cols[i]: st.image(get_img_url(card), use_container_width=True)
    with c_turn:
        st.markdown("**TURN**")
        if len(cards) >= 4: st.image(get_img_url(cards[3]), width=80)
    with c_river:
        st.markdown("**RIVER**")
        if len(cards) >= 5: st.image(get_img_url(cards[4]), width=80)

def render_specific_hand_builder(player_key):
    col1, col2, col3 = st.columns([1, 1, 1])
    suits_ui = [('♠', 's'), ('♥', 'h'), ('♦', 'd'), ('♣', 'c')]
    ranks_ui = list("AKQJT98765432")
    with col1:
        r1 = st.selectbox("Rank", ranks_ui, key=f"{player_key}_r1")
        s1 = next(x[1] for x in suits_ui if x[0] == st.selectbox("Suit", [x[0] for x in suits_ui], key=f"{player_key}_s1"))
    with col2:
        r2 = st.selectbox("Rank", ranks_ui, key=f"{player_key}_r2")
        s2 = next(x[1] for x in suits_ui if x[0] == st.selectbox("Suit", [x[0] for x in suits_ui], key=f"{player_key}_s2"))
    with col3:
        st.write(""); st.write("")
        if st.button("Add", key=f"{player_key}_add"):
            hand_str = f"{r1}{s1}{r2}{s2}"
            current = st.session_state.get(f"{player_key}_range_val", "")
            st.session_state[f"{player_key}_range_val"] = (current + ", " + hand_str).strip(", ")
            st.rerun()

# ==========================================
# 計算ロジック
# ==========================================
def calculate_equity(hero_range, villain_range, board, iterations=1000, silent=False):
    h_wins = 0; ties = 0
    full_deck = []
    for r in "23456789TJQKA":
        for s in "shdc": full_deck.append(str_to_card(r+s))
    if not hero_range or not villain_range: return 0.0
    if not silent: prog = st.progress(0)
    for i in range(iterations):
        hh = random.choice(hero_range); vh = random.choice(villain_range)
        used = set(board) | set(hh) | set(vh)
        if len(used) != len(board) + 4: continue
        rem = [c for c in full_deck if c not in used]
        need = 5 - len(board)
        if need < 0: need = 0
        if len(rem) < need: continue
        run = random.sample(rem, need) if need > 0 else []
        final_board = board + run
        hs = evaluator.evaluate(final_board, hh)
        vs = evaluator.evaluate(final_board, vh)
        if hs < vs: h_wins += 1
        elif hs == vs: ties += 1
        if not silent and i % (iterations//10+1)==0: prog.progress((i+1)/iterations)
    if not silent: prog.empty()
    return (h_wins + ties/2) / iterations * 100

def analyze_runouts(hero_range, villain_range, board, iterations=500):
    full_deck = []
    for r in "23456789TJQKA":
        for s in "shdc": full_deck.append(str_to_card(r+s))
    deck = [c for c in full_deck if c not in board]
    res = []
    status = st.empty(); status.caption(f"Calculating Heatmap ({iterations} iter/card)...")
    prog = st.progress(0); total = len(deck)
    for idx, c in enumerate(deck):
        eq = calculate_equity(hero_range, villain_range, board + [c], iterations, True)
        c_str = card_to_str(c)
        res.append({"Card": c_str, "Rank": c_str[0], "Suit": c_str[1], "Equity": eq})
        prog.progress((idx+1)/total)
    prog.empty(); status.empty()
    return pd.DataFrame(res)

def analyze_range_distribution(hero_range, villain_range, board, iterations=500):
    st.caption(f"Calculating Distribution ({iterations} iterations)...")
    size = 100
    hs = random.sample(hero_range, size) if len(hero_range)>size else hero_range
    vs = random.sample(villain_range, size) if len(villain_range)>size else villain_range
    he = [calculate_equity([h], villain_range, board, iterations, True) for h in hs]
    ve = [calculate_equity([h], hero_range, board, iterations, True) for h in vs]
    return he, ve

# ==========================================
# UI
# ==========================================
st.title("Poker Range Analyzer ♠ (Treys Edition)")

with st.container():
    st.subheader("1. Range Setup")
    col_h, col_v = st.columns(2)
    with col_h:
        st.markdown("**Hero Range**")
        tab_h1, tab_h2 = st.tabs(["📊 Macro (%)", "🃏 Specific"])
        with tab_h1:
            def update_hero():
                s, e = st.session_state.hero_slider
                st.session_state.hero_range_val = get_range_string_from_percent(s, e)
            st.slider("Range %", 0, 100, (0, 10), key="hero_slider", on_change=update_hero)
        with tab_h2: render_specific_hand_builder("hero")
        hero_input = st.text_area("Hero Input", key="hero_range_val", height=70)
        h_combos = parse_range_notation(hero_input)
        if h_combos:
            st.caption(f"{len(h_combos)} combos")
            grid_h = create_range_grid_visual(h_combos)
            lbl = list("AKQJT98765432")
            fig_h = px.imshow(grid_h, x=lbl, y=lbl, color_continuous_scale=["lightgrey", "blue"], zmin=0, zmax=1)
            
            # --- 修正箇所: type='category' を追加 ---
            fig_h.update_xaxes(side="top", type='category')
            fig_h.update_yaxes(autorange="reversed", type='category')
            # ------------------------------------
            
            fig_h.update_layout(width=200, height=200, margin=dict(l=0,r=0,t=0,b=0), coloraxis_showscale=False)
            st.plotly_chart(fig_h, use_container_width=False)
    with col_v:
        st.markdown("**Villain Range**")
        tab_v1, tab_v2 = st.tabs(["📊 Macro (%)", "🃏 Specific"])
        with tab_v1:
            def update_villain():
                s, e = st.session_state.villain_slider
                st.session_state.villain_range_val = get_range_string_from_percent(s, e)
            st.slider("Range %", 0, 100, (0, 15), key="villain_slider", on_change=update_villain)
        with tab_v2: render_specific_hand_builder("villain")
        villain_input = st.text_area("Villain Input", key="villain_range_val", height=70)
        v_combos = parse_range_notation(villain_input)
        if v_combos:
            st.caption(f"{len(v_combos)} combos")
            grid_v = create_range_grid_visual(v_combos)
            lbl = list("AKQJT98765432")
            fig_v = px.imshow(grid_v, x=lbl, y=lbl, color_continuous_scale=["lightgrey", "red"], zmin=0, zmax=1)
            
            # --- 修正箇所: type='category' を追加 ---
            fig_v.update_xaxes(side="top", type='category')
            fig_v.update_yaxes(autorange="reversed", type='category')
            # ------------------------------------
            
            fig_v.update_layout(width=200, height=200, margin=dict(l=0,r=0,t=0,b=0), coloraxis_showscale=False)
            st.plotly_chart(fig_v, use_container_width=False)

st.subheader("2. Board Setup")
with st.expander("Show Card Picker", expanded=True):
    suits_data = [('s', '♠', 'grey'), ('h', '♥', 'red'), ('d', '♦', 'blue'), ('c', '♣', 'green')]
    ranks_data = list("AKQJT98765432")
    for s_code, s_icon, s_color in suits_data:
        row_cols = st.columns([0.5, 12])
        with row_cols[0]: st.markdown(f"## :{s_color}[{s_icon}]")
        with row_cols[1]:
            cols = st.columns(13)
            for i, r in enumerate(ranks_data):
                card_str = f"{r}{s_code}"
                is_sel = card_str in st.session_state['board_cards']
                def toggle(c=card_str):
                    curr = st.session_state['board_cards']
                    if c in curr: curr.remove(c)
                    else: 
                        if len(curr) < 5: curr.append(c)
                    st.session_state['widget_id_counter'] += 1
                cols[i].button(f"{r}", key=f"btn_{card_str}", type="primary" if is_sel else "secondary", on_click=toggle)

st.divider()
board_list_str = st.session_state['board_cards']
col_vis, col_ctrl = st.columns([4, 1])
with col_vis:
    try:
        board_objs = [str_to_card(s) for s in board_list_str] if board_list_str else []
        display_board_streets(board_objs)
    except: st.error("Board Error. Reset."); board_objs = []
with col_ctrl:
    if st.button("Clear Board"): st.session_state['board_cards'] = []; st.rerun()

st.divider()
hero_range = parse_range_notation(hero_input)
villain_range = parse_range_notation(villain_input)

if hero_range and villain_range:
    eq = calculate_equity(hero_range, villain_range, board_objs, iterations=sim_iterations)
    c1,c2,c3 = st.columns([1,2,1])
    with c1: st.metric("Hero Win%", f"{eq:.1f}%")
    with c2: st.progress(eq/100)
    
    st.divider()
    st.subheader("3. Dynamic Board Analysis (Next Card)")
    with st.expander("ℹ️ How to read (解説)", expanded=False):
        st.markdown("""
        * **Weighted Downside Risk:** Sum of equity loss across bad cards.
        * **Scare Cards:** Cards that drop equity by >5%.
        """)
    if len(board_objs) < 5:
        df = analyze_runouts(hero_range, villain_range, board_objs, iterations=sim_iterations)
        df['Loss'] = eq - df['Equity']
        bad_cards = df[df['Loss'] > 0]
        weighted_risk = bad_cards['Loss'].sum()
        scare_cards_count = len(bad_cards[bad_cards['Loss'] > 5.0])
        safe_count = len(df) - len(bad_cards)
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1: st.metric("Weighted Downside Risk", f"{weighted_risk:.1f}")
        with col_m2: st.metric("Scare Cards (>5% Drop)", f"{scare_cards_count}")
        with col_m3: st.metric("Safe/Good Cards", f"{safe_count}")

        order = list("AKQJT98765432")
        piv = df.pivot_table(index="Rank", columns="Suit", values="Equity").reindex(order)[list("shdc")]
        fig = px.imshow(piv, x=['s♠','h♥','d♦','c♣'], y=order, color_continuous_scale="RdBu_r", zmin=0, zmax=100, text_auto=".0f")
        fig.update_yaxes(type='category', dtick=1)
        fig.update_layout(width=400, height=600, title="Next Card Heatmap")
        
        sel = st.plotly_chart(fig, on_select="rerun", key=f"hm_{len(board_objs)}", selection_mode="points")
        if sel and len(sel["selection"]["points"])>0:
            pt = sel["selection"]["points"][0]
            nc = f"{pt['y']}{pt['x'][0]}"
            if nc not in st.session_state['board_cards']:
                st.session_state['board_cards'].append(nc)
                st.session_state['widget_id_counter'] += 1
                st.rerun()

        st.divider()
        st.subheader("4. Range Distribution")
        he, ve = analyze_range_distribution(hero_range, villain_range, board_objs, iterations=sim_iterations)
        if he and ve:
            hist = go.Figure()
            hist.add_trace(go.Histogram(x=he, name='Hero', marker_color='blue', opacity=0.7, xbins=dict(start=0,end=100,size=5)))
            hist.add_trace(go.Histogram(x=ve, name='Villain', marker_color='red', opacity=0.7, xbins=dict(start=0,end=100,size=5)))
            hist.update_layout(barmode='overlay', width=800, height=400, xaxis_title="Equity %")
            st.plotly_chart(hist)
    else: st.success("River Reached")
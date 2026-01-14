import streamlit as st
import random
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from treys import Card, Evaluator
from collections import Counter

st.set_page_config(page_title="Poker Equity Tool", layout="wide")

# ==========================================
# CSS: レイアウト調整
# ==========================================
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 3rem !important;
    }
    /* ボタンのスタイル調整 */
    .stButton button {
        width: 100%;
    }
    
    /* ボード画像 (Flexbox) */
    .board-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100%;
    }
    .board-label {
        font-size: 0.8rem;
        font-weight: bold;
        margin-bottom: 2px;
        text-align: center;
        width: 100%;
    }
    .board-cards-row {
        display: flex;
        justify-content: center;
        gap: 4px;
        width: 100%;
        min-height: 50px;
        background-color: #f0f2f6; /* 空の時の背景 */
        border-radius: 5px;
        padding: 5px;
    }
    .board-card-img {
        width: 30%;
        max-width: 60px;
        height: auto;
        border-radius: 4px;
        box-shadow: 1px 1px 3px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# Treys評価機
@st.cache_resource
def load_evaluator(): return Evaluator()
try:
    with st.spinner('Loading engine...'): evaluator = load_evaluator()
except: st.stop()

# ==========================================
# State管理
# ==========================================
with st.sidebar:
    st.header("🔧 Settings")
    sim_iterations = st.slider("Iterations", 100, 5000, 500, 100)
    if st.button("Reset", type="primary"):
        for k in st.session_state.keys(): del st.session_state[k]
        st.rerun()

if 'board_cards' not in st.session_state: st.session_state['board_cards'] = ["Th", "8d", "2c"]
if 'hero_range_val' not in st.session_state: st.session_state.hero_range_val = "QQ+, AKs, AKo"
if 'villain_range_val' not in st.session_state: st.session_state.villain_range_val = "TT+, AJs+, KQs, AQo+"

# ==========================================
# ユーティリティ
# ==========================================
HAND_ORDER = [
    "AA", "KK", "QQ", "AKs", "JJ", "AKo", "AQs", "TT", "AJs", "KQs", "99", "ATs", "AQo", "KJs", "88", "QJs", "JTs", "AJo", "KQo", "77", "ATo", "KTs", "QTs", "T9s", "KJo", "QJo", "J9s", "98s", "66", "A9s", "A5s", "A8s", "K9s", "Q9s", "JTo", "55", "A4s", "A7s", "A3s", "T8s", "87s", "A2s", "K8s", "Q8s", "J8s", "44", "A9o", "KTo", "QTo", "97s", "76s", "33", "22", "A6s", "K7s", "Q7s", "J7s", "T7s", "86s", "65s", "A8o", "K9o", "Q9o", "J9o", "T9o", "K6s", "Q6s", "J6s", "T6s", "96s", "75s", "54s", "A5o", "A7o", "K8o", "Q8o", "J8o", "T8o", "98o", "87o", "K5s", "Q5s", "J5s", "T5s", "95s", "85s", "64s", "A4o", "A6o", "K7o", "Q7o", "J7o", "T7o", "97o", "76o", "K4s", "Q4s", "J4s", "T4s", "94s", "84s", "74s", "53s", "A3o", "A2o", "65o", "54o", "K3s", "Q3s", "J3s", "T3s", "93s", "83s", "73s", "63s", "43s", "K2s", "Q2s", "J2s", "T2s", "92s", "82s", "72s", "62s", "52s", "42s", "32s", "K6o", "Q6o", "J6o", "T6o", "96o", "86o", "75o", "64o", "53o", "K5o", "Q5o", "J5o", "T5o", "95o", "85o", "74o", "63o", "52o", "43o", "K4o", "Q4o", "J4o", "T4o", "94o", "84o", "73o", "62o", "42o", "32o", "K3o", "Q3o", "J3o", "T3o", "93o", "83o", "72o", "K2o", "Q2o", "J2o", "T2o", "92o", "82o"
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

# HTML Board Display
def display_board_streets(cards):
    def get_html_img(card_int):
        c_str = card_to_str(card_int)
        r = c_str[0].upper().replace("T", "0"); s = c_str[1].upper()
        url = f"https://deckofcardsapi.com/static/img/{r}{s}.png"
        return f'<img src="{url}" class="board-card-img">'

    c_flop, c_turn, c_river = st.columns([3, 1.2, 1.2])
    
    with c_flop:
        img_html = "".join([get_html_img(c) for c in cards[:3]]) if len(cards)>0 else "&nbsp;"
        st.markdown(f'<div class="board-container"><div class="board-label">FLOP</div><div class="board-cards-row">{img_html}</div></div>', unsafe_allow_html=True)
            
    with c_turn:
        img_html = get_html_img(cards[3]) if len(cards)>=4 else "&nbsp;"
        st.markdown(f'<div class="board-container"><div class="board-label">TURN</div><div class="board-cards-row">{img_html}</div></div>', unsafe_allow_html=True)
            
    with c_river:
        img_html = get_html_img(cards[4]) if len(cards)>=5 else "&nbsp;"
        st.markdown(f'<div class="board-container"><div class="board-label">RIVER</div><div class="board-cards-row">{img_html}</div></div>', unsafe_allow_html=True)

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
# ポップアップ・ボードセレクター (核心部分)
# ==========================================
@st.dialog("🃏 Select Board Cards")
def edit_board_dialog():
    st.caption("Select cards to add/remove. (Max 5 cards)")
    
    # スートをタブで切り替え（これでスマホでも縦長にならない！）
    tab_s, tab_h, tab_d, tab_c = st.tabs(["♠ Spades", "♥ Hearts", "♦ Diamonds", "♣ Clubs"])
    
    ranks = list("AKQJT98765432")
    
    # 共通のボタン描画関数
    def render_suit_grid(suit_code):
        # 4列で表示
        cols = st.columns(4)
        for i, r in enumerate(ranks):
            card_str = f"{r}{suit_code}"
            is_sel = card_str in st.session_state['board_cards']
            
            def toggle(c=card_str):
                curr = st.session_state['board_cards']
                if c in curr: curr.remove(c)
                else: 
                    if len(curr) < 5: curr.append(c)
                st.rerun() # ダイアログ内を再描画
                
            # 選択中は色を変える
            btn_type = "primary" if is_sel else "secondary"
            # どの列に入れるか (i % 4)
            cols[i % 4].button(f"{r}", key=f"d_btn_{card_str}", type=btn_type, on_click=toggle)

    with tab_s: render_suit_grid('s')
    with tab_h: render_suit_grid('h')
    with tab_d: render_suit_grid('d')
    with tab_c: render_suit_grid('c')
    
    st.divider()
    if st.button("Close & Apply", type="primary"):
        st.rerun() # ダイアログを閉じてメイン画面更新

# ==========================================
# Logic
# ==========================================
def calculate_equity(hero_range, villain_range, board, iterations=1000, silent=False):
    h_wins = 0; ties = 0; full_deck = []
    for r in "23456789TJQKA":
        for s in "shdc": full_deck.append(str_to_card(r+s))
    if not hero_range or not villain_range: return 0.0
    for i in range(iterations):
        hh = random.choice(hero_range); vh = random.choice(villain_range)
        used = set(board) | set(hh) | set(vh)
        if len(used) != len(board) + 4: continue
        rem = [c for c in full_deck if c not in used]
        need = 5 - len(board); 
        if need < 0: need = 0
        if len(rem) < need: continue
        run = random.sample(rem, need) if need > 0 else []
        final_board = board + run
        hs = evaluator.evaluate(final_board, hh)
        vs = evaluator.evaluate(final_board, vh)
        if hs < vs: h_wins += 1
        elif hs == vs: ties += 1
    return (h_wins + ties/2) / iterations * 100

def analyze_runouts(hero_range, villain_range, board, iterations=500):
    full_deck = []
    for r in "23456789TJQKA":
        for s in "shdc": full_deck.append(str_to_card(r+s))
    deck = [c for c in full_deck if c not in board]
    res = []
    status = st.empty(); status.caption(f"Analyzing... ({iterations} iter)")
    prog = st.progress(0); total = len(deck)
    for idx, c in enumerate(deck):
        eq = calculate_equity(hero_range, villain_range, board + [c], iterations, True)
        c_str = card_to_str(c)
        res.append({"Card": c_str, "Rank": c_str[0], "Suit": c_str[1], "Equity": eq})
        prog.progress((idx+1)/total)
    prog.empty(); status.empty()
    return pd.DataFrame(res)

def analyze_range_distribution(hero_range, villain_range, board, iterations=500):
    size = 100
    hs = random.sample(hero_range, size) if len(hero_range)>size else hero_range
    vs = random.sample(villain_range, size) if len(villain_range)>size else villain_range
    he = [calculate_equity([h], villain_range, board, iterations, True) for h in hs]
    ve = [calculate_equity([h], hero_range, board, iterations, True) for h in vs]
    return he, ve

# ==========================================
# Main UI
# ==========================================
st.title("Poker Range Analyzer ♠")

# Range
with st.container():
    st.subheader("1. Range")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Hero")
        tab1, tab2 = st.tabs(["%", "Card"])
        with tab1:
            def up_h(): st.session_state.hero_range_val = get_range_string_from_percent(*st.session_state.hs)
            st.slider("Hero %", 0, 100, (0,10), key="hs", on_change=up_h)
        with tab2: render_specific_hand_builder("hero")
        hero_in = st.text_area("H", key="hero_range_val", height=60, label_visibility="collapsed")
        h_combos = parse_range_notation(hero_in)
        if h_combos:
            fig = px.imshow(create_range_grid_visual(h_combos), color_continuous_scale=["lightgrey", "blue"], zmin=0, zmax=1)
            fig.update_xaxes(side="top", type='category'); fig.update_yaxes(autorange="reversed", type='category')
            fig.update_layout(width=150, height=150, margin=dict(l=0,r=0,t=0,b=0), coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=False)
    with c2:
        st.caption("Villain")
        tab1, tab2 = st.tabs(["%", "Card"])
        with tab1:
            def up_v(): st.session_state.villain_range_val = get_range_string_from_percent(*st.session_state.vs)
            st.slider("Villain %", 0, 100, (0,15), key="vs", on_change=up_v)
        with tab2: render_specific_hand_builder("villain")
        villain_in = st.text_area("V", key="villain_range_val", height=60, label_visibility="collapsed")
        v_combos = parse_range_notation(villain_in)
        if v_combos:
            fig = px.imshow(create_range_grid_visual(v_combos), color_continuous_scale=["lightgrey", "red"], zmin=0, zmax=1)
            fig.update_xaxes(side="top", type='category'); fig.update_yaxes(autorange="reversed", type='category')
            fig.update_layout(width=150, height=150, margin=dict(l=0,r=0,t=0,b=0), coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=False)

# Board (New Pop-up Style)
st.divider()
st.subheader("2. Board")

col_bd_btn, col_bd_view = st.columns([1, 3])
with col_bd_btn:
    if st.button("🃏 Edit Board", type="primary", use_container_width=True):
        edit_board_dialog()
    if st.button("Clear", use_container_width=True):
        st.session_state['board_cards'] = []
        st.rerun()

with col_bd_view:
    try:
        board_objs = [str_to_card(s) for s in st.session_state['board_cards']]
        display_board_streets(board_objs)
    except: st.error("Error")

# Analysis
st.divider()
hero_range = parse_range_notation(hero_in)
villain_range = parse_range_notation(villain_in)

if hero_range and villain_range:
    eq = calculate_equity(hero_range, villain_range, board_objs, iterations=sim_iterations)
    c1,c2,c3 = st.columns([1,2,1])
    with c1: st.metric("Win%", f"{eq:.1f}%")
    with c2: st.progress(eq/100)
    
    st.subheader("3. Dynamics")
    if len(board_objs) < 5:
        df = analyze_runouts(hero_range, villain_range, board_objs, iterations=sim_iterations)
        df['Loss'] = eq - df['Equity']
        bad = df[df['Loss'] > 0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Risk", f"{bad['Loss'].sum():.1f}")
        c2.metric("Scare", f"{len(bad[bad['Loss']>5])}")
        c3.metric("Safe", f"{len(df)-len(bad)}")

        order = list("AKQJT98765432")
        piv = df.pivot_table(index="Rank", columns="Suit", values="Equity").reindex(order)[list("shdc")]
        fig = px.imshow(piv, x=['s♠','h♥','d♦','c♣'], y=order, color_continuous_scale="RdBu_r", zmin=0, zmax=100, text_auto=".0f")
        fig.update_layout(width=300, height=500, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        he, ve = analyze_range_distribution(hero_range, villain_range, board_objs, iterations=sim_iterations)
        hist = go.Figure()
        hist.add_trace(go.Histogram(x=he, name='Hero', marker_color='blue', opacity=0.7))
        hist.add_trace(go.Histogram(x=ve, name='Villain', marker_color='red', opacity=0.7))
        hist.update_layout(barmode='overlay', width=300, height=300, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(hist, use_container_width=True)
    else: st.success("River Reached")

import streamlit as st
import pandas as pd
import time
from datetime import datetime
import sqlite3
import plotly.express as px

# --- Configuration & Setup ---
st.set_page_config(page_title="Poker Host CRM v2.2", page_icon="♠️", layout="wide")

# --- Database Integration ---
DB_NAME = "poker_crm.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            game_mode TEXT,
            total_buyin REAL,
            total_cash_out REAL,
            gross_house_profit REAL,
            expenses REAL,
            net_profit REAL,
            my_share REAL,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_session_to_db(mode, buyin, cashout, gross, expenses, net, share, notes):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO sessions 
        (timestamp, game_mode, total_buyin, total_cash_out, gross_house_profit, expenses, net_profit, my_share, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ts, mode, buyin, cashout, gross, expenses, net, share, notes))
    conn.commit()
    conn.close()

def get_analytics_data():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM sessions", conn)
    conn.close()
    return df

# Initialize DB on load
init_db()

# --- Session State ---
if 'players' not in st.session_state:
    st.session_state['players'] = {}
if 'start_time' not in st.session_state:
    st.session_state['start_time'] = time.time()
if 'log' not in st.session_state:
    st.session_state['log'] = []
    
# V2.1/V2.2 Accounting State
if 'expenses_log' not in st.session_state:
    st.session_state['expenses_log'] = [] # List of {time, item, amount}
if 'rake_log' not in st.session_state:
    st.session_state['rake_log'] = [] # List of {time, event, amount}
if 'insurance_log' not in st.session_state:
    st.session_state['insurance_log'] = [] # List of {time, outcome, details, amount}

if 'income_rake' not in st.session_state:
    st.session_state['income_rake'] = 0.0
if 'income_insurance' not in st.session_state:
    st.session_state['income_insurance'] = 0.0
    
if 'fee_cash_collected' not in st.session_state:
    st.session_state['fee_cash_collected'] = 0.0
if 'game_mode' not in st.session_state:
    st.session_state['game_mode'] = "Time Charge (Venue Fee)"

# Helper
def log_event(event, amount, type_):
    st.session_state['log'].append({
        "Time": datetime.now().strftime("%H:%M:%S"),
        "Event": event,
        "Amount": f"${amount:,.0f}",
        "Type": type_
    })

# --- Translations (V2.2 Updates) ---
translations = {
    "English": {
        "nav_header": "Navigation",
        "nav_home": "♠️ Active Session",
        "nav_analytics": "📊 Analytics Dashboard",
        "gamemode_header": "Game Mode",
        "mode_time": "Time Charge (Venue Fee)",
        "mode_rake": "Rake Game (Profit Share)",
        "sidebar_header": "🔧 Chip Config",
        "app_title": "🃏 Poker Host CRM v2.2",
        "live_header": "🎲 Active Players",
        "rebuy": "Re-buy",
        "cashout": "Cash Out",
        "fee": "Venue Fee",
        "fee_deduct": "Deduct Stack",
        "fee_cash": "Paid Cash",
        "summary": "📊 Session Summary",
        "save_session": "💾 Save Session to DB",
        "saved": "Session Saved!",
        "analytics_title": "📈 Profit Analytics",
        "kpi_lifetime": "Lifetime Profit",
        "kpi_sessions": "Total Sessions",
        "kpi_avg": "Avg Profit/Session",
        "chip_white": "White", "chip_red": "Red", "chip_black": "Black", "chip_purple": "Purple", "chip_yellow": "Yellow",
        "tab_expenses": "💸 Expenses",
        "tab_income": "💰 Income & Risk",
        "lbl_item": "Item Name",
        "lbl_amount": "Amount",
        "btn_add_exp": "Add Expense",
        "lbl_rake": "Rake Collection",
        "btn_add_rake": "Add Rake",
        "lbl_ins": "Insurance / Risk",
        "btn_add_ins": "Add Amount",
        "total_rake": "Total Rake",
        "total_ins": "Total Insurance",
        "total_exp": "Total Expenses",
        "gross_income": "Gross Income",
        "net_profit": "Net Profit",
        "my_share": "My Share",
        "partner_share": "Partner Share",
        "pct_share": "Host Share %",
        "notes": "Session Notes",
        "reset": "Reset All Data",
        "confirm_out": "Confirm & Out",
        "still_owes": "Still Owes",
        # V2.2 Risk
        "ins_calc": "🧮 Insurance Calculator",
        "ins_bet": "Bet Amount",
        "ins_outs": "Outs (1-20)",
        "ins_odds": "Odds",
        "ins_payout": "Potential Payout",
        "btn_win": "✅ House Win (Keep Bet)",
        "btn_loss": "❌ House Loss (Pay Out)",
        "log_rake": "📜 Rake History",
        "log_ins": "📉 Insurance History",
        "lang_sel": "Language / 語言"
    },
    "繁體中文": {
        "nav_header": "功能導覽",
        "nav_home": "♠️ 當前牌局",
        "nav_analytics": "📊 數據中心",
        "gamemode_header": "經營模式",
        "mode_time": "計時局 (收清潔費)",
        "mode_rake": "抽水局 (股東分潤)",
        "sidebar_header": "🔧 籌碼設定",
        "app_title": "🃏 撲克局務管理 v2.2",
        "live_header": "🎲 在桌玩家",
        "rebuy": "加買",
        "cashout": "結算離桌",
        "fee": "清潔費",
        "fee_deduct": "籌碼扣除",
        "fee_cash": "另外付現",
        "summary": "📊 結算總表",
        "save_session": "💾 保存牌局記錄",
        "saved": "記錄已保存！",
        "analytics_title": "📈 獲利分析報表",
        "kpi_lifetime": "生涯總獲利",
        "kpi_sessions": "總場次",
        "kpi_avg": "場均獲利",
        "chip_white": "白色", "chip_red": "紅色", "chip_black": "黑色", "chip_purple": "紫色", "chip_yellow": "黃色",
        "tab_expenses": "💸 支出明細",
        "tab_income": "💰 收入與風控",
        "lbl_item": "項目名稱",
        "lbl_amount": "金額",
        "btn_add_exp": "新增支出",
        "lbl_rake": "抽水管理",
        "btn_add_rake": "新增抽水",
        "lbl_ins": "保險 / 風控管理",
        "btn_add_ins": "手動新增金額",
        "total_rake": "總抽水",
        "total_ins": "總保險獲利",
        "total_exp": "總支出",
        "gross_income": "總營收",
        "net_profit": "淨利潤",
        "my_share": "我的分潤",
        "partner_share": "股東分潤",
        "pct_share": "主辦佔比 %",
        "notes": "備註",
        "reset": "重置所有資料",
        "confirm_out": "確認結算",
        "still_owes": "尚欠款項",
        # V2.2 Risk
        "ins_calc": "🧮 保險計算器",
        "ins_bet": "玩家買保險金額",
        "ins_outs": "補牌數 (Outs)",
        "ins_odds": "賠率",
        "ins_payout": "潛在賠付額",
        "btn_win": "✅ 沒中 (莊贏收錢)",
        "btn_loss": "❌ 中了 (莊賠付錢)",
        "log_rake": "📜 抽水記錄",
        "log_ins": "📉 保險流水",
        "lang_sel": "Language / 語言"
    }
}

# --- Sidebar ---
st.sidebar.header("Settings") 
# We need to render the language selector first to update 't' immediately
lang = st.sidebar.radio("Language / 語言", ["English", "繁體中文"], horizontal=True, label_visibility="collapsed")
t = translations[lang]

st.sidebar.divider()
st.sidebar.header(t["nav_header"])
page = st.sidebar.radio("Go to", ["Home", "Analytics"], label_visibility="collapsed")

# --- PAGE: ANALYTICS ---
if page == "Analytics":
    st.title(t["analytics_title"])
    df = get_analytics_data()
    
    if not df.empty:
        # KPIs
        total_profit = df['my_share'].sum()
        total_sessions = len(df)
        avg_profit = df['my_share'].mean()
        
        k1, k2, k3 = st.columns(3)
        k1.metric(t["kpi_lifetime"], f"${total_profit:,.0f}")
        k2.metric(t["kpi_sessions"], total_sessions)
        k3.metric(t["kpi_avg"], f"${avg_profit:,.0f}")
        
        # Charts
        st.divider()
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("💰 Growth Curve")
            # Cumulative Sum
            df['cumulative_profit'] = df['my_share'].cumsum()
            fig = px.line(df, x='timestamp', y='cumulative_profit', markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.subheader("🎲 Game Modes")
            fig2 = px.pie(df, names='game_mode', values='my_share', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
            
        # Data Table
        st.dataframe(df.style.format("${:,.0f}", subset=["total_buyin", "net_profit", "my_share"]), use_container_width=True)
    else:
        st.info("No saved sessions yet.")

# --- PAGE: HOME (Active Session) ---
else:
    # Game Mode Selection
    st.sidebar.header(t["gamemode_header"])
    # Map selection back to key for consistency
    mode_options = [t["mode_time"], t["mode_rake"]]
    curr_mode = st.session_state.get('game_mode_label', mode_options[0])
    if curr_mode not in mode_options: curr_mode = mode_options[0] # Fallback if lang changed
    
    game_mode_sel = st.sidebar.radio("Mode", mode_options, index=mode_options.index(curr_mode) if curr_mode in mode_options else 0)
    st.session_state['game_mode_label'] = game_mode_sel
    # Persist the internal key
    if game_mode_sel == t["mode_time"]: st.session_state['game_mode'] = "Time Charge"
    else: st.session_state['game_mode'] = "Rake Game"
    
    # Chip Config
    st.sidebar.header(t["sidebar_header"])
    chip_config = {}
    chip_def = {"white": ("⚪", 5), "red": ("🔴", 25), "black": ("⚫", 100), "purple": ("🟣", 500), "yellow": ("🟡", 1000)}
    for k, v in chip_def.items():
        chip_config[k] = st.sidebar.number_input(f"{t[f'chip_{k}']} ({v[0]})", value=v[1], step=5, key=f"cfg_{k}")
        
    st.title(t["app_title"])
    
    # 1. Add Player
    with st.expander("👤 Add Player", expanded=False):
        c1, c2, c3, c4 = st.columns([2,1,1,1])
        new_name = c1.text_input("Name")
        new_cash = c2.number_input("Cash In", step=100)
        new_credit = c3.number_input("Credit In", step=100)
        if c4.button("Add"):
            if new_name:
                st.session_state['players'][new_name] = {
                    "cash_in": new_cash, "credit_in": new_credit, 
                    "chip_counts": {k:0 for k in chip_config}, 
                    "status": "active", "final_stack": 0, "final_payout": 0
                }
                st.rerun()

    # 2. Active Players
    st.subheader(t["live_header"])
    active = {n:p for n,p in st.session_state['players'].items() if p['status']=='active'}
    
    for name, data in active.items():
        with st.expander(f"**{name}** (${data['cash_in']+data['credit_in']:,})"):
            c_chips, c_acts = st.columns([3, 1])
            
            # Re-buy
            with c_acts.popover(t["rebuy"]):
                amt = st.number_input("Amt", step=100, key=f"rb_{name}")
                if st.button("Confirm", key=f"btn_rb_{name}"):
                    data['cash_in'] += amt
                    log_event(f"{name} Rebuy", amt, "Cash")
                    st.rerun()
            
            # Chips
            stack = 0
            cols = c_chips.columns(5)
            for i, (k, v) in enumerate(chip_config.items()):
                cnt = cols[i].number_input(f"${v}", value=data['chip_counts'][k], key=f"c_{name}_{k}")
                data['chip_counts'][k] = cnt
                stack += cnt * v
            c_chips.metric("Stack", f"${stack:,.0f}")
            
            # Cash Out
            st.divider()
            co1, co2, co3 = st.columns([1,1,1])
            
            # Venue Fee Logic
            fee = 0
            if st.session_state['game_mode'] == "Time Charge":
                fee = co1.number_input(t["fee"], value=170, step=10, key=f"fee_{name}")
                fee_method = co2.radio("Method", [t["fee_deduct"], t["fee_cash"]], key=f"fm_{name}")
            else:
                fee_method = "N/A"
            
            if co3.button(t["cashout"], key=f"btn_co_{name}"):
                payout_stack = stack
                if st.session_state['game_mode'] == "Time Charge":
                    if fee_method == t["fee_deduct"]:
                        payout_stack = max(0, stack - fee)
                        st.session_state['income_rake'] += fee 
                        st.session_state['rake_log'].append({"Time": datetime.now().strftime("%H:%M"), "Event": f"{name} Fee", "Amount": fee})
                        log_event(f"{name} Fee (Deduct)", fee, "Fee")
                    else:
                        st.session_state['income_rake'] += fee
                        st.session_state['fee_cash_collected'] += fee
                        st.session_state['rake_log'].append({"Time": datetime.now().strftime("%H:%M"), "Event": f"{name} Fee (Cash)", "Amount": fee})
                        log_event(f"{name} Fee (Cash)", fee, "Fee")
                
                # Debt logic
                debt_cleared = min(payout_stack, data['credit_in'])
                cash_payout = payout_stack - debt_cleared
                
                # Update
                data['final_stack'] = stack
                data['final_payout'] = cash_payout
                data['status'] = 'out'
                st.rerun()

    # 3. Summary & Financials (V2.2)
    st.markdown("---")
    st.header(t["summary"])
    
    # Financial Management Tabs
    tab_exp, tab_inc = st.tabs([t["tab_expenses"], t["tab_income"]])
    
    # --- EXPENSES ---
    with tab_exp:
        ec1, ec2, ec3 = st.columns([2, 1, 1])
        exp_item = ec1.text_input(t["lbl_item"], key="exp_new_item")
        exp_amt = ec2.number_input(t["lbl_amount"], step=100.0, key="exp_new_amt")
        if ec3.button(t["btn_add_exp"]):
             if exp_item and exp_amt > 0:
                 st.session_state['expenses_log'].append({
                     "Time": datetime.now().strftime("%H:%M"),
                     "Item": exp_item,
                     "Amount": exp_amt
                 })
                 st.rerun()
        
        if st.session_state['expenses_log']:
            st.dataframe(pd.DataFrame(st.session_state['expenses_log']), use_container_width=True)
            
    # --- INCOME & RISK ---
    with tab_inc:
        ic1, ic2 = st.columns([1, 1.2]) # Bigger column for calc
        
        # --- LEFT: RAKE ---
        with ic1:
            st.subheader(t["lbl_rake"])
            new_rake = st.number_input("+ $", step=100.0, key="new_rake_in")
            if st.button(t["btn_add_rake"]):
                if new_rake > 0:
                    st.session_state['income_rake'] += new_rake
                    st.session_state['rake_log'].append({
                        "Time": datetime.now().strftime("%H:%M"), 
                        "Event": "Manual Rake", 
                        "Amount": new_rake
                    })
                    st.rerun()
            
            st.metric(t["total_rake"], f"${st.session_state['income_rake']:,.0f}")
            
            st.caption(t["log_rake"])
            if st.session_state['rake_log']:
                 st.dataframe(pd.DataFrame(st.session_state['rake_log'][::-1]), use_container_width=True, height=200)

        # --- RIGHT: INSURANCE ---
        with ic2:
            st.subheader(t["lbl_ins"])
            
            # Risk Calculator
            with st.expander(t["ins_calc"], expanded=True):
                ins_bet = st.number_input(t["ins_bet"], min_value=0.0, step=100.0, key="ins_bet_val")
                # Outs slider 1-20
                ins_outs = st.slider(t["ins_outs"], 1, 20, 4)
                
                # Standard Odds Dict
                odds_map = {1:30, 2:16, 3:10, 4:8, 5:6, 6:5, 7:4.5, 8:4, 9:3.5, 10:3, 11:2.6, 12:2.3, 13:2, 14:1.8, 15:1.6, 16:1.4}
                curr_odd = odds_map.get(ins_outs, 1.2)
                
                payout = ins_bet * curr_odd
                
                c_cal1, c_cal2 = st.columns(2)
                c_cal1.metric(t["ins_odds"], f"1:{curr_odd}")
                c_cal2.metric(t["ins_payout"], f"${payout:,.0f}")
                
                b_win, b_loss = st.columns(2)
                if b_win.button(t["btn_win"], use_container_width=True):
                    if ins_bet > 0:
                        st.session_state['income_insurance'] += ins_bet
                        st.session_state['insurance_log'].append({
                            "Time": datetime.now().strftime("%H:%M"),
                            "Action": "Win (沒中)",
                            "Details": f"Bet ${ins_bet} on {ins_outs} Outs",
                            "Change": f"+${ins_bet}"
                        })
                        st.rerun()
                
                if b_loss.button(t["btn_loss"], use_container_width=True):
                    if ins_bet > 0:
                        st.session_state['income_insurance'] -= payout
                        st.session_state['insurance_log'].append({
                            "Time": datetime.now().strftime("%H:%M"),
                            "Action": "Loss (中了)",
                            "Details": f"Pay limit 1:{curr_odd}",
                            "Change": f"-${payout}"
                        })
                        st.rerun()

            # Manual Add Override
            with st.popover(t["btn_add_ins"]):
                manual_ins = st.number_input("Manual Amount (+)", step=100.0)
                if st.button("Add Manual"):
                    st.session_state['income_insurance'] += manual_ins
                    st.session_state['insurance_log'].append({"Time": datetime.now().strftime("%H:%M"), "Action": "Manual", "Details": "-", "Change": f"+${manual_ins}"})
                    st.rerun()

            st.metric(t["total_ins"], f"${st.session_state['income_insurance']:,.0f}")
            
            st.caption(t["log_ins"])
            if st.session_state['insurance_log']:
                st.dataframe(pd.DataFrame(st.session_state['insurance_log'][::-1]), use_container_width=True, height=200)


    # --- FINAL CALCULATIONS ---
    st.divider()
    
    total_rake = st.session_state['income_rake']
    total_ins = st.session_state['income_insurance']
    total_exp = sum(x['Amount'] for x in st.session_state['expenses_log'])
    
    gross_income = total_rake + total_ins
    net_profit = gross_income - total_exp
    
    # Display Breakdown
    b1, b2, b3, b4 = st.columns(4)
    b1.metric(t["gross_income"], f"${gross_income:,.0f}")
    b2.metric(t["total_exp"], f"${total_exp:,.0f}")
    b3.metric(t["net_profit"], f"${net_profit:,.0f}", delta_color="normal" if net_profit >= 0 else "inverse")
    
    # Profit Sharing
    host_pct = 100
    if st.session_state['game_mode'] == "Rake Game":
        host_pct = st.slider(t["pct_share"], 0, 100, 60)
        
    my_share = net_profit * (host_pct / 100.0)
    partner_share = net_profit - my_share
    
    b4.metric(t["my_share"], f"${my_share:,.0f}")
    if partner_share != 0:
        st.info(f"{t['partner_share']}: ${partner_share:,.0f}")

    # SAVE SESSION
    notes = st.text_input(t["notes"])
    if st.button(t["save_session"], type="primary"):
        # Append expense details to notes for record keeping
        exp_details = "; ".join([f"{x['Item']}:${x['Amount']}" for x in st.session_state['expenses_log']])
        final_notes = f"{notes} | Exp: {exp_details}"
        
        total_buyin = sum(p['cash_in']+p['credit_in'] for p in st.session_state['players'].values())
        total_payout = sum(p['final_payout'] for p in st.session_state['players'].values() if p['status']=='out')
        
        save_session_to_db(st.session_state['game_mode'], total_buyin, total_payout, gross_income, total_exp, net_profit, my_share, final_notes)
        st.success(t["saved"])
        st.balloons()
        
    # Reset
    if st.button(t["reset"]):
        st.session_state.clear()
        st.rerun()

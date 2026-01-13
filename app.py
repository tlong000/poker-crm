import streamlit as st
import pandas as pd
import time
from datetime import datetime
import plotly.express as px
import json
from streamlit_gsheets import GSheetsConnection
import extra_streamlit_components as stx

# --- Configuration & Setup ---
st.set_page_config(page_title="Poker Host CRM v5.5", page_icon="♠️", layout="wide")

# --- Google Sheets Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. Constants & Setup ---
KEYS_TO_PERSIST = [
    'players', 'log', 'expenses_log', 'rake_log', 'insurance_log', 
    'income_rake', 'income_insurance', 'game_mode', 'fee_cash_collected', 'start_time'
]



# --- FLIGHT RECORDER FUNCTIONS (Persistence) ---
def sync_state_to_cloud():
    """Saves current session state to 'active_state' worksheet"""
    if not st.session_state.get('authenticated'): return

    # 1. Gather State (Dynamic)
    state_payload = {k: st.session_state.get(k) for k in KEYS_TO_PERSIST}
    
    json_str = json.dumps(state_payload)
    host_id = st.session_state.get('host_id')
    if not host_id: return

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 2. Safe Sync Wrapper
    try:
        # Read Existing
        try:
            df_state = conn.read(worksheet="active_state", ttl=0)
        except:
            df_state = pd.DataFrame(columns=["Host_ID", "Last_Update", "State_JSON"])
            
        # Upsert
        new_row = {"Host_ID": host_id, "Last_Update": now_str, "State_JSON": json_str}
        
        if not df_state.empty and "Host_ID" in df_state.columns:
            if host_id in df_state["Host_ID"].values:
                df_state.loc[df_state["Host_ID"] == host_id, ["Last_Update", "State_JSON"]] = [now_str, json_str]
            else:
                df_state = pd.concat([df_state, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df_state = pd.DataFrame([new_row])
            
        # Push
        conn.update(worksheet="active_state", data=df_state)
    except Exception as e:
        # V6.0 Safe Sync: Log error but don't crash app
        print(f"Sync failed (Non-critical): {e}")

def restore_state_from_cloud():
    """Restores session state from 'active_state' worksheet if exists"""
    try:
        host_id = st.session_state.get('host_id')
        if not host_id: return False

        try:
            df_state = conn.read(worksheet="active_state", ttl=0)
        except:
            return False # Sheet doesn't exist
        
        if not df_state.empty and "Host_ID" in df_state.columns:
            row = df_state[df_state["Host_ID"] == host_id]
            if not row.empty:
                json_str = row.iloc[0]["State_JSON"]
                if not json_str: return False

                payload = json.loads(json_str)
                
                # Restore Keys (Dynamic)
                for k in KEYS_TO_PERSIST:
                    if k in payload:
                        st.session_state[k] = payload[k]
                
                st.toast("🔄 Game State Restored from Cloud", icon="☁️")
                return True
    except Exception as e:
        print(f"Restore failed: {e}")
    return False

def wipe_snapshot():
    """Clears persistence for current host"""
    try:
        host_id = st.session_state.get('host_id')
        df_state = conn.read(worksheet="active_state", ttl=0)
        if not df_state.empty and "Host_ID" in df_state.columns:
            # Drop row
            df_state = df_state[df_state["Host_ID"] != host_id]
            conn.update(worksheet="active_state", data=df_state)
    except:
        pass

def get_analytics_data():
    try:
        df = conn.read(ttl="10s")
        current_host = st.session_state.get('host_id')
        if not df.empty and 'Host_ID' in df.columns:
            df = df[df['Host_ID'] == current_host]
        return df
    except:
        return pd.DataFrame()

def save_session_to_cloud(mode, buyin, cashout, gross, expenses, net, share, notes):
    existing_data = conn.read(ttl="10s")
    new_row = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Host_ID": st.session_state.get('host_id', 'unknown'),
        "Mode": mode,
        "Total_Buyin": buyin,
        "Total_Cashout": cashout,
        "Gross_Profit": gross,
        "Expenses": expenses,
        "Net_Profit": net,
        "My_Share": share,
        "Notes": notes
    }])
    if existing_data.empty:
        updated_df = new_row
    else:
        updated_df = pd.concat([existing_data, new_row], ignore_index=True)
    conn.update(data=updated_df)
    st.cache_data.clear()

# --- 1. Initialize Cookie Manager ---
cookie_manager = stx.CookieManager(key="auth_cookie_manager")

# --- 2. Session State Initialization ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'host_id' not in st.session_state:
    st.session_state['host_id'] = None
if 'just_logged_out' not in st.session_state:
    st.session_state['just_logged_out'] = False

# --- 3. Load Secrets ---
try:
    HOSTS = st.secrets["hosts"]
except Exception as e:
    st.error("Missing secrets.toml")
    st.stop()

# --- 4. Auto-Login Logic (The Guarded Gate) ---
# Only attempt auto-login if:
# A. We are NOT authenticated
# B. We did NOT just log out (The Fix)
cookie_token = None
try:
    cookie_token = cookie_manager.get("host_token")
except:
    pass

if not st.session_state['authenticated'] and not st.session_state['just_logged_out']:
    if cookie_token:
        # Check if cookie matches a valid user
        found_user = None
        for uid, upw in HOSTS.items():
            if cookie_token == uid: # In prod, use a hash, but this works for now
                found_user = uid
                break
        
        if found_user:
            st.session_state['authenticated'] = True
            st.session_state['host_id'] = found_user
            # We do NOT rerun here to avoid weird loops, just let the app flow
            st.toast(f"⚡ Auto-logged in as {found_user}")
            time.sleep(0.5)

# --- 5. Logout Logic (In Sidebar) ---
if st.session_state['authenticated']:
    st.sidebar.divider()
    st.sidebar.caption(f"User: {st.session_state['host_id']}")
    if st.sidebar.button("🚪 Logout", type="primary"):
        # A. Delete Cookie
        try:
            cookie_manager.delete("host_token")
        except:
            pass
        
        # B. Clear Session
        st.session_state['authenticated'] = False
        st.session_state['host_id'] = None
        
        # C. ACTIVATE THE LOCK (Crucial)
        st.session_state['just_logged_out'] = True
        
        # D. Rerun to show login page
        st.rerun()

# --- 6. Manual Login Page ---
if not st.session_state['authenticated']:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("🔒 Poker CRM Login")
        uid = st.text_input("Host ID")
        upw = st.text_input("Password", type="password")
        remember = st.checkbox("Remember Me / 記住我")
        
        if st.button("Log In", type="primary", use_container_width=True):
            if uid in HOSTS and HOSTS[uid] == upw:
                st.session_state['authenticated'] = True
                st.session_state['host_id'] = uid
                st.session_state['just_logged_out'] = False # Reset lock
                
                if remember:
                    cookie_manager.set("host_token", uid, key="set_cookie", expires_at=datetime.now() + pd.Timedelta(days=7))
                else:
                    # If they didn't check remember, ensure no old cookie remains
                    try:
                        cookie_manager.delete("host_token")
                    except:
                        pass
                
                # Restore Data
                if restore_state_from_cloud():
                     st.toast("Session Restored!", icon="🔄")
                
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Invalid ID or Password")
    
    st.stop() # Stop execution here if not logged in 

# --- SESSION STATE DEFAULTS ---
# Initialize defaults only if keys don't exist (i.e. not restored)
defaults = {
    'players': {},
    'start_time': time.time(),
    'log': [],
    'expenses_log': [],
    'rake_log': [],
    'insurance_log': [],
    'income_rake': 0.0,
    'income_insurance': 0.0,
    'fee_cash_collected': 0.0,
    'game_mode': "Time Charge (Venue Fee)"
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Helper
def log_event(event, amount, type_):
    st.session_state['log'].append({
        "Time": datetime.now().strftime("%H:%M:%S"),
        "Event": event,
        "Amount": f"${amount:,.0f}",
        "Type": type_
    })
    sync_state_to_cloud() # Auto-Save on Log

# --- Translations ---
translations = {
    "English": {
        "nav_header": "Navigation",
        "nav_home": "♠️ Active Session",
        "nav_analytics": "📊 Analytics Dashboard",
        "gamemode_header": "Game Mode",
        "mode_time": "Time Charge (Venue Fee)",
        "mode_rake": "Rake Game (Profit Share)",
        "sidebar_header": "🔧 Chip Config",
        "app_title": "🃏 Poker Host CRM v5.5",
        "live_header": "🎲 Active Players",
        "paused_header": "🟡 Paused / Sit Out",
        "history_header": "⚫ Cashed Out History",
        "rebuy": "Re-buy",
        "sit_out": "Sit Out", 
        "return_seat": "Return",
        "cashout": "Cash Out",
        "fee": "Venue Fee",
        "fee_deduct": "Deduct Stack",
        "fee_cash": "Paid Cash",
        "summary": "📊 Session Summary",
        "save_session": "💾 Save Session to Cloud",
        "saved": "Session Saved to GSheets!",
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
        "ins_calc": "🧮 Insurance Calculator",
        "ins_bet": "Bet Amount",
        "ins_outs": "Outs (1-20)",
        "ins_odds": "Odds",
        "ins_payout": "Potential Payout",
        "btn_win": "✅ House Win (Keep Bet)",
        "btn_loss": "❌ House Loss (Pay Out)",
        "log_rake": "📜 Rake History",
        "log_ins": "📉 Insurance History",
        "pay_player": "🟢 Pay Player",
        "player_owes": "🔴 Player Owes",
        "audit_ok": "✅ System Balanced",
        "audit_short": "🔴 SHORTAGE DETECTED",
        "audit_surplus": "🟡 SURPLUS DETECTED",
        "repay": "💰 Repay",
        "btn_repay": "Confirm Repay"
    },
    "繁體中文": {
        "nav_header": "功能導覽",
        "nav_home": "♠️ 當前牌局",
        "nav_analytics": "📊 數據中心",
        "gamemode_header": "經營模式",
        "mode_time": "計時局 (收清潔費)",
        "mode_rake": "抽水局 (股東分潤)",
        "sidebar_header": "🔧 籌碼設定",
        "app_title": "🃏 撲克局務管理 v5.5",
        "live_header": "🎲 在桌玩家",
        "paused_header": "🟡 暫離 / Sit Out",
        "history_header": "⚫ 已離桌記錄",
        "rebuy": "加買",
        "sit_out": "暫離",
        "return_seat": "回桌",
        "cashout": "結算離桌",
        "fee": "清潔費",
        "fee_deduct": "籌碼扣除",
        "fee_cash": "另外付現",
        "summary": "📊 結算總表",
        "save_session": "💾 保存牌局記錄 (雲端)",
        "saved": "記錄已上傳 Google Sheets！",
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
        "ins_calc": "🧮 保險計算器",
        "ins_bet": "玩家買保險金額",
        "ins_outs": "補牌數 (Outs)",
        "ins_odds": "賠率",
        "ins_payout": "潛在賠付額",
        "btn_win": "✅ 沒中 (莊贏收錢)",
        "btn_loss": "❌ 中了 (莊賠付錢)",
        "log_rake": "📜 抽水記錄",
        "log_ins": "📉 保險流水",
        "pay_player": "🟢 應付玩家",
        "player_owes": "🔴 玩家回補",
        "audit_ok": "✅ 系統平衡 (無帳差)",
        "audit_short": "🔴 警告：帳目短缺 (少籌碼)",
        "audit_surplus": "🟡 警告：帳目盈餘 (多籌碼)",
        "repay": "💰 還款 (轉現金)",
        "btn_repay": "確認還款"
    }
}

# --- Chip Config (Helper for Audit) ---
def get_chip_config():
    return {
        "white": st.session_state.get("cfg_white", 5),
        "red": st.session_state.get("cfg_red", 25),
        "black": st.session_state.get("cfg_black", 100),
        "purple": st.session_state.get("cfg_purple", 500),
        "yellow": st.session_state.get("cfg_yellow", 1000)
    }

# --- Sidebar ---
st.sidebar.header("Settings") 


    # Manual Force Save
    if st.sidebar.button("💾 Force Flight Recorder"):
        sync_state_to_cloud()
        st.toast("State Saved Manually")

lang = st.sidebar.radio("Language / 語言", ["English", "繁體中文"], horizontal=True, label_visibility="collapsed")
t = translations[lang]

st.sidebar.divider()
st.sidebar.header(t["nav_header"])
page = st.sidebar.radio("Go to", ["Home", "Analytics"], label_visibility="collapsed")

# --- ADMIN MODE (V3.1.2) ---
if st.sidebar.checkbox("🔧 Admin Mode"):
    st.sidebar.warning("⚠️ God Mode Active")
    uploaded_file = st.sidebar.file_uploader("Import CSV", type=["csv"])
    if uploaded_file is not None:
        if st.sidebar.button("⚠️ Overwrite Data", type="primary"):
            try:
                # 1. Read CSV
                df_import = pd.read_csv(uploaded_file)
                
                # 2. Clear Current State
                st.session_state['players'] = {}
                
                # 3. Repopulate
                # ExpectedCols: Name, Buy-in, Final Stack, Payout, Fee Paid
                for index, row in df_import.iterrows():
                    p_name = str(row['Name'])
                    p_buyin = float(row['Buy-in']) 
                    p_stack = float(row['Final Stack'])
                    p_payout = float(row['Payout'])
                    p_fee = float(row.get('Fee Paid', 0)) 
                    
                    st.session_state['players'][p_name] = {
                        "cash_in": p_buyin, 
                        "credit_in": 0.0, 
                        "chip_counts": {k:0 for k in get_chip_config()}, 
                        "status": "out", 
                        "final_stack": p_stack, 
                        "final_payout": p_payout, 
                        "final_fee": p_fee
                    }
                sync_state_to_cloud() # Auto-Save on Import
                st.sidebar.success(f"Imported {len(df_import)} players!")
                time.sleep(1) 
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

# --- PAGE: ANALYTICS ---
if page == "Analytics":
    st.title(t["analytics_title"])
    df = get_analytics_data()
    
    if not df.empty:
        total_profit = df['My_Share'].sum()
        total_sessions = len(df)
        avg_profit = df['My_Share'].mean()
        
        k1, k2, k3 = st.columns(3)
        k1.metric(t["kpi_lifetime"], f"${total_profit:,.0f}")
        k2.metric(t["kpi_sessions"], total_sessions)
        k3.metric(t["kpi_avg"], f"${avg_profit:,.0f}")
        
        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("💰 Growth Curve")
            df['cumulative_profit'] = df['My_Share'].cumsum()
            fig = px.line(df, x='Timestamp', y='cumulative_profit', markers=True)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("🎲 Game Modes")
            fig2 = px.pie(df, names='Mode', values='My_Share', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(df.style.format("${:,.0f}", subset=["Total_Buyin", "Net_Profit", "My_Share"]), use_container_width=True)
    else:
        st.info("No saved sessions in cloud.")

# --- PAGE: HOME (Active Session) ---
else:
    # Game Mode Selection
    st.sidebar.header(t["gamemode_header"])
    mode_options = [t["mode_time"], t["mode_rake"]]
    curr_mode = st.session_state.get('game_mode_label', mode_options[0])
    if curr_mode not in mode_options: curr_mode = mode_options[0]
    
    game_mode_sel = st.sidebar.radio("Mode", mode_options, index=mode_options.index(curr_mode) if curr_mode in mode_options else 0)
    st.session_state['game_mode_label'] = game_mode_sel
    
    # Internal Mode Key
    new_mode = "Time Charge" if game_mode_sel == t["mode_time"] else "Rake Game"
    if st.session_state['game_mode'] != new_mode:
        st.session_state['game_mode'] = new_mode
        sync_state_to_cloud() # Save on mode change
    
    # Chip Config
    st.sidebar.header(t["sidebar_header"])
    chip_config = {}
    chip_def = {"white": ("⚪", 5), "red": ("🔴", 25), "black": ("⚫", 100), "purple": ("🟣", 500), "yellow": ("🟡", 1000)}
    for k, v in chip_def.items():
        chip_config[k] = st.sidebar.number_input(f"{t[f'chip_{k}']} ({v[0]})", value=v[1], step=5, key=f"cfg_{k}")
        
    st.title(t["app_title"])

    # --- V6.0 HIGH-LEVEL METRICS (CALCULATION) ---
    total_inflow = sum(p['cash_in'] + p['credit_in'] for p in st.session_state['players'].values())
    
    # Audit Logic
    chips_on_table = 0
    for p in st.session_state['players'].values():
        if p['status'] in ['active', 'paused']:
            s = sum(p['chip_counts'][k] * chip_config[k] for k in chip_config)
            chips_on_table += s
            
    total_final_stacks = sum(p.get('final_stack', 0) for p in st.session_state['players'].values() if p['status'] == 'out')
    total_fees_in_rake = sum(p.get('final_fee', 0) for p in st.session_state['players'].values() if p['status']=='out' and p.get('final_fee', 0) > 0)
    
    pot_rake = st.session_state['income_rake'] - total_fees_in_rake
    gross_insurance = st.session_state['income_insurance']
    
    total_outflow = chips_on_table + total_final_stacks + pot_rake + gross_insurance
    discrepancy = total_inflow - total_outflow

    # Dashboard Metrics
    total_exp = sum(x['Amount'] for x in st.session_state['expenses_log'])
    net_profit_house = (st.session_state['income_rake'] + st.session_state['income_insurance']) - total_exp

    # --- V6.0 DASHBOARD UI ---
    m1, m2, m3 = st.columns(3)
    m1.metric("🎲 Active Chips (Pot)", f"${chips_on_table:,.0f}")
    m2.metric("💰 House Profit", f"${net_profit_house:,.0f}", delta_color="normal")
    
    if discrepancy == 0:
        m3.metric("✅ Audit Status", "OK", delta="Balanced", delta_color="normal")
    elif discrepancy > 0:
        m3.metric("🔴 Audit Status", f"SHORT: -${discrepancy:,.0f}", delta="Missing", delta_color="inverse")
    else:
        m3.metric("🟡 Audit Status", f"SURPLUS: +${abs(discrepancy):,.0f}", delta="Extra", delta_color="off")

    st.divider()

    # --- APP BODY ---
    
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
                    "status": "active", "final_stack": 0, "final_payout": 0, "final_fee": 0
                }
                sync_state_to_cloud()
                st.rerun()

    # 2. Active Players
    st.subheader(t["live_header"])
    active = {n:p for n,p in st.session_state['players'].items() if p['status']=='active'}
    paused = {n:p for n,p in st.session_state['players'].items() if p['status']=='paused'}
    
    if not active:
        st.info("No active players.")

    for name, data in active.items():
        total_in = data['cash_in'] + data['credit_in']
        with st.expander(f"**{name}** (${total_in:,}) [Cash: ${data['cash_in']:,} | Credit: ${data['credit_in']:,}]", expanded=True):
            c_chips, c_acts = st.columns([3, 1])
            
            with c_acts:
                # Re-buy
                with st.popover(t["rebuy"]):
                    amt = st.number_input("Amt", step=100, key=f"rb_{name}")
                    if st.button("Confirm", key=f"btn_rb_{name}"):
                        data['cash_in'] += amt 
                        log_event(f"{name} Rebuy", amt, "Cash")
                        # sync_state_to_cloud called in log_event
                        st.rerun()
                
                # Repay (V3.2)
                with st.popover(t["repay"]):
                    if data['credit_in'] > 0:
                        rep_amt = st.number_input("Amount", step=100.0, max_value=float(data['credit_in']), key=f"rep_{name}")
                        if st.button(t['btn_repay'], key=f"btn_rep_{name}"):
                            if rep_amt > 0:
                                data['credit_in'] -= rep_amt
                                data['cash_in'] += rep_amt
                                log_event(f"{name} Repaid Debt", rep_amt, "Repay")
                                st.rerun()
                    else:
                        st.info("No Debt")

                # Sit Out
                if st.button(t["sit_out"], key=f"so_{name}"):
                    data['status'] = 'paused'
                    sync_state_to_cloud()
                    st.rerun()

            # Chips
            stack = 0
            cols = c_chips.columns(5)
            changed_chips = False
            for i, (k, v) in enumerate(chip_config.items()):
                cnt = cols[i].number_input(f"${v}", value=data['chip_counts'][k], key=f"c_{name}_{k}")
                if cnt != data['chip_counts'][k]:
                    data['chip_counts'][k] = cnt
                    changed_chips = True
            
            if changed_chips:
                # We don't auto-save on every chip click to avoid spamming API, 
                # but maybe should? Let's rely on Manual Save or major events for now.
                # Or maybe save if they close the expander? Hard to detect.
                # Let's add a "Update Stack" button or just trust the next event saves it.
                # Actually, Streamlit reruns on every change, so we COULD save.
                # But rate limits... Let's save on Sidebar "Force Save" or major events.
                pass

            stack = sum(data['chip_counts'][k] * chip_config[k] for k in chip_config)
            c_chips.metric("Stack", f"${stack:,.0f}")
            
            # Cash Out
            st.divider()
            co1, co2, co3 = st.columns([1,1,1])
            
            # Venue Fee Logic
            fee = 0
            fee_method = "N/A"
            if st.session_state['game_mode'] == "Time Charge":
                fee = co1.number_input(t["fee"], value=170, step=10, key=f"fee_{name}")
                fee_method = co2.radio("Method", [t["fee_deduct"], t["fee_cash"]], key=f"fm_{name}")
            
            # --- REAL TIME NET CALCULATION ---
            if st.session_state['game_mode'] == "Time Charge" and fee_method == t["fee_deduct"]:
                proj_payout_stack = max(0, stack - fee)
            else:
                proj_payout_stack = stack
            
            credit_debt = data['credit_in']
            debt_cleared = min(proj_payout_stack, credit_debt)
            proj_cash_payout = proj_payout_stack - debt_cleared
            proj_remaining_debt = credit_debt - debt_cleared
            
            with co3:
                # Visual Alerts
                if proj_remaining_debt > 0:
                    st.error(f"{t['player_owes']}: ${proj_remaining_debt:,.0f}")
                else:
                    st.success(f"{t['pay_player']}: ${proj_cash_payout:,.0f}")
                
                if st.button(t["cashout"], key=f"btn_co_{name}", type="primary"):
                    payout_stack = proj_payout_stack
                    
                    # Record Fee
                    if st.session_state['game_mode'] == "Time Charge":
                        if fee_method == t["fee_deduct"]:
                             st.session_state['income_rake'] += fee 
                             st.session_state['rake_log'].append({"Time": datetime.now().strftime("%H:%M"), "Event": f"{name} Fee", "Amount": fee})
                             log_event(f"{name} Fee", fee, "Fee")
                        else:
                             st.session_state['income_rake'] += fee
                             st.session_state['fee_cash_collected'] += fee
                             st.session_state['rake_log'].append({"Time": datetime.now().strftime("%H:%M"), "Event": f"{name} Fee (Cash)", "Amount": fee})
                             log_event(f"{name} Fee (Cash)", fee, "Fee")
                    
                    data['final_stack'] = stack
                    data['final_payout'] = proj_cash_payout
                    data['final_fee'] = fee
                    data['status'] = 'out'
                    sync_state_to_cloud()
                    st.rerun()

    # Paused Players
    if paused:
        st.markdown("---")
        with st.expander(t["paused_header"], expanded=True):
            for name, data in paused.items():
                pc1, pc2 = st.columns([4, 1])
                pc1.info(f"**{name}** (Buy-in: ${data['cash_in']+data['credit_in']:,}) - Paused")
                if pc2.button(t["return_seat"], key=f"ret_{name}"):
                    data['status'] = 'active'
                    sync_state_to_cloud()
                    st.rerun()

    # 3. Summary & Financials
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
                 sync_state_to_cloud()
                 st.rerun()
        if st.session_state['expenses_log']:
            st.dataframe(pd.DataFrame(st.session_state['expenses_log']), use_container_width=True)
            
    # --- INCOME & RISK ---
    with tab_inc:
        show_rake = (st.session_state['game_mode'] == "Rake Game")
        
        if show_rake:
            ic1, ic2 = st.columns([1, 1.2])
        else:
            ic2 = st.container()
            ic1 = None

        # --- RAKE (Conditional) ---
        if show_rake and ic1:
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
                        sync_state_to_cloud()
                        st.rerun()
                st.metric(t["total_rake"], f"${st.session_state['income_rake']:,.0f}")
                st.caption(t["log_rake"])
                if st.session_state['rake_log']:
                     st.dataframe(pd.DataFrame(st.session_state['rake_log'][::-1]), use_container_width=True, height=200)

        # --- INSURANCE ---
        with ic2:
            st.subheader(t["lbl_ins"])
            with st.expander(t["ins_calc"], expanded=True):
                ins_bet = st.number_input(t["ins_bet"], min_value=0.0, step=100.0, key="ins_bet_val")
                ins_outs = st.slider(t["ins_outs"], 1, 20, 4)
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
                            "Time": datetime.now().strftime("%H:%M"), "Action": "Win (沒中)", "Details": f"Bet ${ins_bet}", "Change": f"+${ins_bet}"
                        })
                        sync_state_to_cloud()
                        st.rerun()
                if b_loss.button(t["btn_loss"], use_container_width=True):
                    if ins_bet > 0:
                        st.session_state['income_insurance'] -= payout
                        st.session_state['insurance_log'].append({
                            "Time": datetime.now().strftime("%H:%M"), "Action": "Loss (中了)", "Details": f"Pay limit", "Change": f"-${payout}"
                        })
                        sync_state_to_cloud()
                        st.rerun()

            with st.popover(t["btn_add_ins"]):
                manual_ins = st.number_input("Manual Amount (+)", step=100.0)
                if st.button("Add Manual"):
                    st.session_state['income_insurance'] += manual_ins
                    st.session_state['insurance_log'].append({"Time": datetime.now().strftime("%H:%M"), "Action": "Manual", "Details": "-", "Change": f"+${manual_ins}"})
                    sync_state_to_cloud()
                    st.rerun()
            st.metric(t["total_ins"], f"${st.session_state['income_insurance']:,.0f}")
            st.caption(t["log_ins"])
            if st.session_state['insurance_log']:
                st.dataframe(pd.DataFrame(st.session_state['insurance_log'][::-1]), use_container_width=True, height=200)

    # Breakdown
    st.divider()
    total_rake = st.session_state['income_rake']
    total_ins = st.session_state['income_insurance']
    total_exp = sum(x['Amount'] for x in st.session_state['expenses_log'])
    gross_income = total_rake + total_ins
    net_profit = gross_income - total_exp
    
    b1, b2, b3, b4 = st.columns(4)
    b1.metric(t["gross_income"], f"${gross_income:,.0f}")
    b2.metric(t["total_exp"], f"${total_exp:,.0f}")
    b3.metric(t["net_profit"], f"${net_profit:,.0f}", delta_color="normal" if net_profit >= 0 else "inverse")
    
    host_pct = 100
    if st.session_state['game_mode'] == "Rake Game":
        host_pct = st.slider(t["pct_share"], 0, 100, 60)
    my_share = net_profit * (host_pct / 100.0)
    partner_share = net_profit - my_share
    b4.metric(t["my_share"], f"${my_share:,.0f}")

    # SAVE SESSION
    notes = st.text_input(t["notes"])
    if st.button(t["save_session"], type="primary"):
        exp_details = "; ".join([f"{x['Item']}:${x['Amount']}" for x in st.session_state['expenses_log']])
        final_notes = f"{notes} | Exp: {exp_details}"
        total_buyin = sum(p['cash_in']+p['credit_in'] for p in st.session_state['players'].values())
        total_payout = sum(p['final_payout'] for p in st.session_state['players'].values() if p['status']=='out')
        
        save_session_to_cloud(st.session_state['game_mode'], total_buyin, total_payout, gross_income, total_exp, net_profit, my_share, final_notes)
        wipe_snapshot() # Clean up persistence after official save
        st.success(t["saved"])
        st.balloons()
        
    # --- Cashed Out History ---
    out_players = [
        {"Name": n, "Buy-in": p['cash_in']+p['credit_in'], "Final Stack": p['final_stack'], "Payout": p['final_payout'], "Fee Paid": p.get('final_fee', 0)}
        for n, p in st.session_state['players'].items() if p['status'] == 'out'
    ]
    if out_players:
        st.markdown("---")
        st.subheader(t["history_header"])
        st.dataframe(pd.DataFrame(out_players), use_container_width=True)

    if st.button(t["reset"]):
        wipe_snapshot() # Wipe cloud
        st.session_state.clear()
        st.rerun()

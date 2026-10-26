import streamlit as st
import pandas as pd
import numpy as np
import datetime
import html as _html
import streamlit.components.v1 as components

# ----------------------------------------------------------------------
# 1. Page Configuration
# ----------------------------------------------------------------------
st.set_page_config(page_title="Gantt Chart chart", layout="wide")
st.title("📊 Gantt Chart chart - ACKD")

# ----- Google Sheet WBS Configuration -----
WBS_SHEET_ID = "1kjQtf7UkFNrgn0imyqAlYEzTPzUbR5evY5lQ8alZUIQ"

# Working week: Sunday to Thursday (Friday & Saturday are the weekend)
NP_WEEKMASK = "1111001"


def build_csv_url(sheet_id, gid=None):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    if gid is not None:
        url += f"&gid={gid}"
    return url


# ----------------------------------------------------------------------
# 2. Load WBS Data
# ----------------------------------------------------------------------
def _pick_col(df, *keys):
    for c in df.columns:
        low = str(c).lower()
        if any(k in low for k in keys):
            return c
    return None


@st.cache_data(ttl=60, show_spinner="Loading WBS from Google Sheet...")
def load_wbs(url):
    df = pd.read_csv(url)
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df = df.dropna(how="all").reset_index(drop=True)

    s_col = _pick_col(df, "start")
    e_col = _pick_col(df, "end")
    df = df.rename(columns={s_col: "Start Date", e_col: "End Date"})
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    df = df.dropna(subset=["Start Date", "End Date"]).reset_index(drop=True)
    return df


# ----------------------------------------------------------------------
# 3. HTML & PDF Renderers
# ----------------------------------------------------------------------
STAGE_COLORS = [
    "#2f6fb3", "#e07b39", "#3a9d6b", "#8e5ea2", "#c9a227",
    "#c0504d", "#3b9aa8", "#7a8b3c", "#b5649a", "#6c7a89",
]

WBS_CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:"Segoe UI",Arial,sans-serif;font-size:12px;color:#1f2933;background:#fff}
.wrap{overflow:auto;height:__H__px;border:1px solid #c9ced6;border-radius:4px;position:relative;background:#fff}
.grid{display:flex;width:__GW__px}
.left{position:sticky;left:0;z-index:6;width:__LW__px;flex:none;background:#fff;border-right:2px solid #9aa4b2}
.right{position:relative;width:__RW__px;flex:none}
.hdr{position:sticky;top:0;z-index:5;height:__HH__px;background:#eef1f5;border-bottom:1px solid #9aa4b2}
.lhdr{display:flex;align-items:flex-end;height:100%}
.lhdr div,.lrow div{padding:0 6px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;flex:none}
.lhdr div{font-weight:600;height:26px;line-height:26px;border-left:1px solid #d3d8df;color:#374151}
.lhdr div:first-child{border-left:none}
.lrow{display:flex;height:__RH__px;border-bottom:1px solid #e3e7ec;align-items:center}
.lrow div{line-height:__RH__px;border-left:1px solid #eef0f3}
.lrow div:first-child{border-left:none}
.lrow.stage{background:#e8edf3;font-weight:700}
.lrow:hover,.rrow:hover{background:#fff8dc}
.lrow.stage:hover{background:#dde5ee}
.c-wbs{width:__W0__px;color:#52606d}
.c-task{width:__W1__px}
.c-date{width:__W2__px;text-align:left}
.c-days{width:__W3__px;text-align:right}
.c-dept{width:__W4__px}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.indent{display:inline-block;width:14px}
.trow{display:flex;height:20px;border-bottom:1px solid #d3d8df}
.trow:last-child{border-bottom:none}
.cell{flex:none;text-align:center;line-height:20px;overflow:hidden;white-space:nowrap;border-left:1px solid #d3d8df;font-size:11px;color:#374151}
.mh{font-weight:600;text-align:left;padding-left:6px}
.wh{text-align:left;padding-left:4px}
.dh{font-size:9px;color:#52606d}
.dh.wk{background:#d9dde3}
.body{position:relative;height:__BH__px;background-image:linear-gradient(to right,transparent 0,transparent __D5__px,rgba(140,150,165,.20) __D5__px,rgba(140,150,165,.20) __D7__px),linear-gradient(to right,#cfd5dd 1px,transparent 1px);background-size:__D7__px 100%,__D7__px 100%;background-repeat:repeat-x}
.rrow{position:relative;height:__RH__px;border-bottom:1px solid #e3e7ec}
.bar{position:absolute;top:6px;height:14px;border-radius:3px;box-shadow:inset 0 -2px 0 rgba(0,0,0,.18)}
.milestone{position:absolute;top:7px;width:12px;height:12px;transform:rotate(45deg);border-radius:1px;box-shadow:0 1px 2px rgba(0,0,0,.25)}
.lbl{position:absolute;top:0;line-height:__RH__px;font-size:10.5px;color:#52606d;white-space:nowrap}
.sum{position:absolute;top:7px;height:6px;background:#1f2933}
.sum:before,.sum:after{content:"";position:absolute;top:6px;border-top:6px solid #1f2933;border-left:5px solid transparent;border-right:5px solid transparent}
.sum:before{left:-1px}
.sum:after{right:-1px}
.today{position:absolute;top:0;bottom:0;width:0;border-left:2px dashed #e03131;z-index:3;pointer-events:none}
"""


def build_wbs_html(df, dw, today):
    esc = lambda v: _html.escape(str(v), quote=True)
    ROW_H, HDR_H = 26, 60
    W = [64, 300, 98, 98, 46, 100]  # WBS | Task | Start | End | Days | Dept
    LW = sum(W)

    origin = df["Start"].min().normalize() - pd.Timedelta(days=2)
    origin = origin - pd.Timedelta(days=(origin.dayofweek + 1) % 7)
    last = df["EndPlus"].max().normalize() + pd.Timedelta(days=12)
    n_days = int((last - origin).days)
    n_days += (-n_days) % 7
    days = pd.date_range(origin, periods=n_days, freq="D")
    RW = n_days * dw

    def x_of(ts):
        return int((pd.Timestamp(ts).normalize() - origin).days * dw)

    def w_of(s, e):
        return max(int(((pd.Timestamp(e).normalize() - pd.Timestamp(s).normalize()).days + 1) * dw), 4)

    fmt = lambda t: pd.Timestamp(t).strftime("%a %d-%b-%y")

    # Header
    months, i = "", 0
    while i < n_days:
        j = i
        while j < n_days and days[j].month == days[i].month:
            j += 1
        label = f"{days[i]:%B %Y}" if (j - i) * dw >= 90 else f"{days[i]:%b %y}"
        months += f'<div class="cell mh" style="width:{(j - i) * dw}px">{label}</div>'
        i = j
    weeks = "".join(
        f'<div class="cell wh" style="width:{7 * dw}px">{days[w]:%d %b}</div>' for w in range(0, n_days, 7)
    )
    show_num = dw >= 14
    day_cells = "".join(
        f'<div class="cell dh{" wk" if d.dayofweek in (4, 5) else ""}" style="width:{dw}px">'
        f'{d.day if show_num else ""}</div>'
        for d in days
    )

    stage_order = df.groupby("Stage")["Start"].min().sort_values().index.tolist()
    color_of = {s: STAGE_COLORS[i % len(STAGE_COLORS)] for i, s in enumerate(stage_order)}

    left_rows, right_rows = [], []
    for stage in stage_order:
        g = df[df["Stage"] == stage].sort_values(["Start", "End"])
        col = color_of[stage]
        s_all, e_all = g["Start Date"].min(), g["End Date"].max()
        wd_all = int(np.busday_count(s_all.date(), e_all.date() + datetime.timedelta(days=1), weekmask=NP_WEEKMASK))

        left_rows.append(
            f'<div class="lrow stage">'
            f'<div class="c-wbs"></div>'
            f'<div class="c-task" style="width:{W[1]}px" title="{esc(stage)}">'
            f'<span class="sw" style="background:{col}"></span>{esc(stage)}</div>'
            f'<div class="c-date">{fmt(s_all)}</div><div class="c-date">{fmt(e_all)}</div>'
            f'<div class="c-days">{wd_all}</div><div class="c-dept"></div></div>'
        )
        ps, pe = g["Start"].min(), g["End"].max()
        right_rows.append(
            f'<div class="rrow"><div class="sum" style="left:{x_of(ps)}px;width:{w_of(ps, pe)}px" '
            f'title="{esc(stage)}: {fmt(s_all)} → {fmt(e_all)}"></div></div>'
        )

        for _, r in g.iterrows():
            is_milestone = r.get("IsMilestone", False)
            tip = (f"{r['Code']}  {r['Task']}\n{fmt(r['Start Date'])}" + 
                   (f" → {fmt(r['End Date'])}\n{r['WorkDays']} working days (Sun-Thu)\n" if not is_milestone else "\n[Milestone]\n") +
                   f"Dept: {r['Disc']}\nResponsible: {r['Resp']}")
            
            left_rows.append(
                f'<div class="lrow">'
                f'<div class="c-wbs" title="{esc(r["Code"])}">{esc(r["Code"])}</div>'
                f'<div class="c-task" title="{esc(r["Task"])}"><span class="indent"></span>'
                f'{"◆ " if is_milestone else ""}{esc(r["Task"])}</div>'
                f'<div class="c-date">{fmt(r["Start Date"])}</div><div class="c-date">{fmt(r["End Date"])}</div>'
                f'<div class="c-days">{r["WorkDays"]}</div>'
                f'<div class="c-dept" title="{esc(r["Disc"])}">{esc(r["Disc"])}</div></div>'
            )

            if is_milestone:
                # وضع علامة المعين (Diamond) في منتصف خانة اليوم
                mx = x_of(r["Start"]) + max(0, (dw // 2) - 6)
                right_rows.append(
                    f'<div class="rrow">'
                    f'<div class="milestone" style="left:{mx}px;background:{col}" title="{esc(tip)}"></div>'
                    f'<div class="lbl" style="left:{mx + 16}px">{esc(r["Resp"])}</div>'
                    f'</div>'
                )
            else:
                bx, bw = x_of(r["Start"]), w_of(r["Start"], r["End"])
                right_rows.append(
                    f'<div class="rrow">'
                    f'<div class="bar" style="left:{bx}px;width:{bw}px;background:{col}" title="{esc(tip)}"></div>'
                    f'<div class="lbl" style="left:{bx + bw + 6}px">{esc(r["Resp"])}</div>'
                    f'</div>'
                )

    n_rows = len(left_rows)
    body_h = n_rows * ROW_H
    comp_h = min(HDR_H + body_h + 4, 720)

    today_html, scroll_x = "", 0
    if origin <= today < last:
        tx = x_of(today) + dw // 2
        today_html = f'<div class="today" style="left:{tx}px"></div>'
        scroll_x = max(0, tx - 250)

    col_titles = ["WBS", "Task Name", "Start", "End", "Days", "Department"]
    col_classes = ["c-wbs", "c-task", "c-date", "c-date", "c-days", "c-dept"]
    lhdr = "".join(
        f'<div class="{c}" style="width:{W[k]}px">{t}</div>'
        for k, (t, c) in enumerate(zip(col_titles, col_classes))
    )

    css = (WBS_CSS.replace("__H__", str(comp_h)).replace("__GW__", str(LW + RW))
           .replace("__LW__", str(LW)).replace("__RW__", str(RW)).replace("__HH__", str(HDR_H))
           .replace("__RH__", str(ROW_H)).replace("__BH__", str(body_h))
           .replace("__D5__", str(5 * dw)).replace("__D7__", str(7 * dw))
           .replace("__W0__", str(W[0])).replace("__W1__", str(W[1])).replace("__W2__", str(W[2]))
           .replace("__W3__", str(W[4])).replace("__W4__", str(W[5])))

    html_doc = (
        f"<style>{css}</style><div class='wrap' id='wrap'><div class='grid'>"
        f"<div class='left'><div class='hdr'><div class='lhdr'>{lhdr}</div></div>{''.join(left_rows)}</div>"
        f"<div class='right'><div class='hdr'>"
        f"<div class='trow'>{months}</div><div class='trow'>{weeks}</div><div class='trow'>{day_cells}</div></div>"
        f

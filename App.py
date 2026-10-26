import streamlit as st
import pandas as pd
import numpy as np
import datetime
from urllib.parse import quote
import html as _html
import streamlit.components.v1 as components

# ----------------------------------------------------------------------
# 1. Page Configuration
# ----------------------------------------------------------------------
st.set_page_config(page_title="Gantt Chart chart", layout="wide")
st.title("📊 Gantt Chart chart - ACKD")

# ----- Google Sheet Configuration -----
WBS_SHEET_ID = "1kjQtf7UkFNrgn0imyqAlYEzTPzUbR5evY5lQ8alZUIQ"
META_SHEET_NAME = "Sheet2"

# Working week: Sunday to Thursday (Friday & Saturday are the weekend)
NP_WEEKMASK = "1111001"


def build_csv_url(sheet_id, gid=None):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    if gid is not None:
        url += f"&gid={gid}"
    return url


def build_sheet_name_url(sheet_id, sheet_name):
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={quote(sheet_name)}"
    )


# ----------------------------------------------------------------------
# 2. Data Loading (WBS & Sheet2 Project Meta)
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


@st.cache_data(ttl=60, show_spinner="Loading Project Info from Sheet2...")
def load_project_meta(sheet_id, sheet_name=META_SHEET_NAME):
    url = build_sheet_name_url(sheet_id, sheet_name)
    meta = {
        "project name": "Gantt Chart chart",
        "project start date": None,
        "project end date": None,
        "note": None,
    }
    try:
        raw = pd.read_csv(url, header=None, dtype=str)
        raw = raw.dropna(how="all")
        n_r, n_c = raw.shape
        for r in range(n_r):
            for c in range(n_c):
                cell = str(raw.iat[r, c]).strip()
                cell_low = cell.lower()
                for k in ["project name", "project start date", "project end date", "note"]:
                    if k in cell_low:
                        val = None
                        # Check right cell
                        for c2 in range(c + 1, n_c):
                            cand = raw.iat[r, c2]
                            if pd.notnull(cand) and str(cand).strip() != "":
                                val = str(cand).strip()
                                break
                        # Check cell below
                        if val is None:
                            for r2 in range(r + 1, n_r):
                                cand = raw.iat[r2, c]
                                if pd.notnull(cand) and str(cand).strip() != "":
                                    val = str(cand).strip()
                                    break
                        if val:
                            meta[k] = val
        return meta
    except Exception:
        return meta


# ----------------------------------------------------------------------
# 3. HTML & PDF Builders
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
    W = [64, 300, 98, 98, 46, 100]
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
        f"<div class='body'>{''.join(right_rows)}{today_html}</div></div>"
        f"</div></div><script>document.getElementById('wrap').scrollLeft={scroll_x};</script>"
    )
    return html_doc, comp_h + 8


def build_wbs_pdf(df, today, meta=None):
    import io
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase.pdfmetrics import stringWidth

    meta = meta or {}
    project_title = meta.get("project name") or "Gantt Chart chart"
    p_start = meta.get("project start date")
    p_end = meta.get("project end date")
    p_note = meta.get("note")

    # Dates text
    dates_part = ""
    if p_start and p_end:
        dates_part = f"Project Dates: {p_start}  →  {p_end}"
    elif p_start:
        dates_part = f"Project Start: {p_start}"
    elif p_end:
        dates_part = f"Project End: {p_end}"

    PW, PH = landscape(A3)
    M = 28
    TITLE_H = 48 if dates_part else 36
    HDR_H = 30

    # ---- Footer note (wrapped into lines) ----
    NOTE_FS = 8
    NOTE_LEAD = 10.5

    def wrap_text(text, font, size, maxw):
        lines = []
        for para in str(text).replace("\r", "").split("\n"):
            words, cur = para.split(), ""
            for w in words:
                trial = (cur + " " + w).strip()
                if stringWidth(trial, font, size) <= maxw:
                    cur = trial
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            lines.append(cur)
        return lines

    note_lines = []
    if p_note:
        note_lines = wrap_text(f"Note*: {p_note}", "Helvetica", NOTE_FS, PW - 2 * M)
        note_lines = note_lines[:6]  # max 6 lines
    NOTE_H = (len(note_lines) * NOTE_LEAD + 8) if note_lines else 0
    FOOT_H = 16 + NOTE_H

    W = [52, 262, 66, 66, 30, 76]
    LW = sum(W)
    TL_W = PW - 2 * M - LW

    origin = df["Start"].min().normalize() - pd.Timedelta(days=2)
    origin = origin - pd.Timedelta(days=(origin.dayofweek + 1) % 7)
    last = df["EndPlus"].max().normalize() + pd.Timedelta(days=18)
    n_days = int((last - origin).days)
    n_days += (-n_days) % 7
    days = pd.date_range(origin, periods=n_days, freq="D")
    dpx = TL_W / n_days
    X0 = M + LW

    x_of = lambda ts: X0 + (pd.Timestamp(ts).normalize() - origin).days * dpx
    w_of = lambda s, e: max(((pd.Timestamp(e).normalize() - pd.Timestamp(s).normalize()).days + 1) * dpx, 1.5)
    fmt = lambda t: pd.Timestamp(t).strftime("%a %d-%b-%y")

    stage_order = df.groupby("Stage")["Start"].min().sort_values().index.tolist()
    color_of = {s: STAGE_COLORS[i % len(STAGE_COLORS)] for i, s in enumerate(stage_order)}
    rows = []
    for stage in stage_order:
        g = df[df["Stage"] == stage].sort_values(["Start", "End"])
        s_all, e_all = g["Start Date"].min(), g["End Date"].max()
        wd = int(np.busday_count(s_all.date(), e_all.date() + datetime.timedelta(days=1), weekmask=NP_WEEKMASK))
        rows.append(("stage", stage, s_all, e_all, wd, g["Start"].min(), g["End"].max(), color_of[stage]))
        for _, r in g.iterrows():
            rows.append(("task", r, color_of[stage]))

    n_rows = len(rows)
    avail = PH - 2 * M - TITLE_H - HDR_H - FOOT_H
    row_h = min(avail / n_rows, 22)
    fs = max(4.5, min(8, row_h * 0.55))
    top = PH - M - TITLE_H
    body_top = top - HDR_H
    body_bot = body_top - n_rows * row_h

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PW, PH))
    c.setTitle(project_title)
    hexc = colors.HexColor

    def fit(text, font, size, maxw):
        text = str(text)
        if stringWidth(text, font, size) <= maxw:
            return text
        while text and stringWidth(text + "...", font, size) > maxw:
            text = text[:-1]
        return text + "..."

    # ---- Header / Title Area ----
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(hexc("#1f2933"))
    c.drawString(M, PH - M - 15, project_title)

    # Sub-data line: Project Start / End dates (the Note is printed at the bottom)
    meta_line = dates_part
    curr_y = PH - M - 27
    if meta_line:
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(hexc("#2b4360"))
        c.drawString(M, curr_y, fit(meta_line, "Helvetica-Bold", 8, PW - 2 * M - 140))
        curr_y -= 11

    c.setFont("Helvetica", 7.5)
    c.setFillColor(hexc("#52606d"))
    c.drawString(M, curr_y, "Grey bands = weekend (Fri & Sat)  |  Diamond = Milestone  |  Black bar = stage summary  |  Red dashed line = today")
    c.drawRightString(PW - M, PH - M - 15, f"Generated: {today:%d-%b-%Y}")

    # Header backgrounds
    c.setFillColor(hexc("#eef1f5"))
    c.rect(M, body_top, LW + TL_W, HDR_H, stroke=0, fill=1)

    for i, row in enumerate(rows):
        if row[0] == "stage":
            c.setFillColor(hexc("#e8edf3"))
            c.rect(M, body_top - (i + 1) * row_h, LW + TL_W, row_h, stroke=0, fill=1)

    c.saveState()
    c.setFillColor(hexc("#8c96a5"))
    c.setFillAlpha(0.20)
    for k, d in enumerate(days):
        if d.dayofweek in (4, 5):
            c.rect(X0 + k * dpx, body_bot, dpx, body_top - body_bot + HDR_H, stroke=0, fill=1)
    c.restoreState()

    c.setStrokeColor(hexc("#cfd5dd"))
    c.setLineWidth(0.4)
    c.setFont("Helvetica", 5.5)
    c.setFillColor(hexc("#374151"))
    for k in range(0, n_days, 7):
        x = X0 + k * dpx
        c.line(x, body_bot, x, body_top)
        c.line(x, body_top, x, body_top + HDR_H / 2)
        lab = f"{days[k]:%d %b}" if 7 * dpx >= 24 else f"{days[k]:%d}"
        c.drawString(x + 2, body_top + 4.5, lab)

    c.setFont("Helvetica-Bold", 7.5)
    i = 0
    while i < n_days:
        j = i
        while j < n_days and days[j].month == days[i].month:
            j += 1
        x, w = X0 + i * dpx, (j - i) * dpx
        c.setStrokeColor(hexc("#9aa4b2"))
        c.line(x, body_top + HDR_H / 2, x, body_top + HDR_H)
        lab = f"{days[i]:%B %Y}" if w >= 70 else (f"{days[i]:%b %y}" if w >= 34 else "")
        c.setFillColor(hexc("#1f2933"))
        c.drawString(x + 3, body_top + HDR_H / 2 + 5, lab)
        i = j
    c.setStrokeColor(hexc("#9aa4b2"))
    c.setLineWidth(0.6)
    c.line(X0, body_top + HDR_H / 2, X0 + TL_W, body_top + HDR_H / 2)

    titles = ["WBS", "Task Name", "Start", "End", "Days", "Department"]
    x = M
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(hexc("#1f2933"))
    for t, w in zip(titles, W):
        if t == "Days":
            c.drawRightString(x + w - 4, body_top + 11, t)
        else:
            c.drawString(x + 4, body_top + 11, t)
        x += w

    for i, row in enumerate(rows):
        y_top = body_top - i * row_h
        y_bot = y_top - row_h
        ty = y_bot + (row_h - fs) / 2 + fs * 0.18
        c.setStrokeColor(hexc("#d9dee5"))
        c.setLineWidth(0.3)
        c.line(M, y_bot, X0 + TL_W, y_bot)

        if row[0] == "stage":
            _, stage, s_all, e_all, wd, ps, pe, col = row
            c.setFillColor(hexc(col))
            c.rect(M + W[0] + 4, y_bot + (row_h - 6) / 2, 6, 6, stroke=0, fill=1)
            c.setFillColor(hexc("#1f2933"))
            c.setFont("Helvetica-Bold", fs)
            c.drawString(M + W[0] + 14, ty, fit(stage, "Helvetica-Bold", fs, W[1] - 18))
            c.drawString(M + W[0] + W[1] + 4, ty, fmt(s_all))
            c.drawString(M + W[0] + W[1] + W[2] + 4, ty, fmt(e_all))
            c.drawRightString(M + sum(W[:5]) - 4, ty, str(wd))

            bx, bw = x_of(ps), w_of(ps, pe)
            bh = max(2.5, row_h * 0.22)
            by = y_bot + (row_h - bh) / 2 + bh * 0.4
            c.setFillColor(hexc("#1f2933"))
            c.rect(bx, by, bw, bh, stroke=0, fill=1)
            tri = bh * 1.1
            for tx in (bx, bx + bw):
                p = c.beginPath()
                p.moveTo(tx - tri * 0.7, by + bh)
                p.lineTo(tx + tri * 0.7, by + bh)
                p.lineTo(tx, by + bh - tri * 1.3)
                p.close()
                c.drawPath(p, stroke=0, fill=1)
        else:
            _, r, col = row
            is_milestone = r.get("IsMilestone", False)

            c.setFillColor(hexc("#52606d"))
            c.setFont("Helvetica", fs)
            c.drawString(M + 4, ty, fit(r["Code"], "Helvetica", fs, W[0] - 6))
            c.setFillColor(hexc("#1f2933"))
            task_label = ("* " if is_milestone else "") + str(r["Task"])
            c.drawString(M + W[0] + 10, ty, fit(task_label, "Helvetica", fs, W[1] - 14))
            c.drawString(M + W[0] + W[1] + 4, ty, fmt(r["Start Date"]))
            c.drawString(M + W[0] + W[1] + W[2] + 4, ty, fmt(r["End Date"]))
            c.drawRightString(M + sum(W[:5]) - 4, ty, str(r["WorkDays"]))
            c.drawString(M + sum(W[:5]) + 4, ty, fit(r["Disc"], "Helvetica", fs, W[5] - 6))

            lab_fs = max(4, fs - 1)
            lab = str(r["Resp"])
            lw = stringWidth(lab, "Helvetica", lab_fs)

            if is_milestone:
                mx = x_of(r["Start"]) + (dpx / 2)
                my = y_bot + (row_h / 2)
                sz = max(3.0, row_h * 0.32)

                c.setFillColor(hexc(col))
                p = c.beginPath()
                p.moveTo(mx, my + sz)
                p.lineTo(mx + sz, my)
                p.lineTo(mx, my - sz)
                p.lineTo(mx - sz, my)
                p.close()
                c.drawPath(p, stroke=0, fill=1)

                c.setFillColor(hexc("#52606d"))
                c.setFont("Helvetica", lab_fs)
                if mx + sz + 3 + lw <= X0 + TL_W:
                    c.drawString(mx + sz + 3, ty, lab)
                else:
                    c.drawRightString(mx - sz - 3, ty, lab)
            else:
                bx, bw = x_of(r["Start"]), w_of(r["Start"], r["End"])
                bh = max(3, row_h * 0.55)
                c.setFillColor(hexc(col))
                c.roundRect(bx, y_bot + (row_h - bh) / 2, bw, bh, min(1.5, bh / 3), stroke=0, fill=1)

                c.setFillColor(hexc("#52606d"))
                c.setFont("Helvetica", lab_fs)
                if bx + bw + 3 + lw <= X0 + TL_W:
                    c.drawString(bx + bw + 3, ty, lab)
                else:
                    c.drawRightString(bx - 3, ty, lab)

    c.setStrokeColor(hexc("#d3d8df"))
    c.setLineWidth(0.3)
    x = M
    for w in W[:-1]:
        x += w
        c.line(x, body_bot, x, body_top + HDR_H)
    c.setStrokeColor(hexc("#9aa4b2"))
    c.setLineWidth(1)
    c.line(X0, body_bot, X0, body_top + HDR_H)

    if origin <= today < last:
        tx = x_of(today) + dpx / 2
        c.setStrokeColor(hexc("#e03131"))
        c.setLineWidth(1.1)
        c.setDash(3, 2)
        c.line(tx, body_bot, tx, body_top + HDR_H)
        c.setDash()
        c.setFont("Helvetica-Bold", 6)
        c.setFillColor(hexc("#e03131"))
        c.drawCentredString(tx, body_bot - 8, "Today")

    c.setStrokeColor(hexc("#9aa4b2"))
    c.setLineWidth(0.8)
    c.rect(M, body_bot, LW + TL_W, body_top - body_bot + HDR_H, stroke=1, fill=0)
    c.line(M, body_top, X0 + TL_W, body_top)

    # ---- Note at the bottom of the page (from Sheet2) ----
    if note_lines:
        ny = body_bot - 20  # below the "Today" label
        c.setStrokeColor(hexc("#9aa4b2"))
        c.setLineWidth(0.5)
        c.line(M, ny + 8, PW - M, ny + 8)
        c.setFont("Helvetica", NOTE_FS)
        c.setFillColor(hexc("#2b4360"))
        for k, line in enumerate(note_lines):
            c.drawString(M, ny - k * NOTE_LEAD, line)

    c.showPage()
    c.save()
    return buf.getvalue()


# ----------------------------------------------------------------------
# 4. Main Interface
# ----------------------------------------------------------------------
wbs_url = build_csv_url(WBS_SHEET_ID)

col_a, col_b = st.columns([1, 3])
with col_a:
    if st.button("🔄 Refresh from Google Sheet", use_container_width=True):
        load_wbs.clear()
        load_project_meta.clear()
        st.rerun()
with col_b:
    st.link_button("🔗 Open Google Sheet", f"https://docs.google.com/spreadsheets/d/{WBS_SHEET_ID}/edit")

# Load Sheet2 meta and WBS data
meta_info = load_project_meta(WBS_SHEET_ID, META_SHEET_NAME)

try:
    df = load_wbs(wbs_url)
    st.success(f"✅ Data loaded. Active Project: **{meta_info.get('project name')}**")
except Exception as e:
    st.error(
        f"Could not read the WBS Google Sheet ({e}). Make sure sharing is set to "
        "'Anyone with the link: Viewer'."
    )
    st.stop()

# Project info card from Sheet2
if any([meta_info.get("project start date"), meta_info.get("project end date"), meta_info.get("note")]):
    with st.container():
        c1, c2, c3 = st.columns([1.5, 1.5, 3])
        c1.caption(f"🗓️ **Start Date:** {meta_info.get('project start date') or '-'}")
        c2.caption(f"🏁 **End Date:** {meta_info.get('project end date') or '-'}")
        c3.caption(f"📝 **Note\\*:** {meta_info.get('note') or '-'}")

code_col = _pick_col(df, "wbs code", "code")
stage_col = _pick_col(df, "stage")
task_col = _pick_col(df, "task", "work package")
disc_col = _pick_col(df, "discipline")
resp_col = _pick_col(df, "responsible")

df = df[df["End Date"] >= df["Start Date"]].copy()
df["IsMilestone"] = (df["Start Date"].dt.date == df["End Date"].dt.date)

# ---- Filters ----
f1, f2, f3, f4 = st.columns([2, 2, 2, 1.4])
with f1:
    if stage_col:
        stages = sorted(df[stage_col].dropna().astype(str).unique())
        sel_stages = st.multiselect("Project Stage", stages, default=stages)
        df = df[df[stage_col].astype(str).isin(sel_stages)]
with f2:
    if disc_col:
        discs = sorted(df[disc_col].dropna().astype(str).unique())
        sel_discs = st.multiselect("Discipline", discs, default=discs)
        df = df[df[disc_col].astype(str).isin(sel_discs)]
with f3:
    hide_done = st.checkbox("Filter completed", value=False)
    snap = st.checkbox(
        "Snap bars to working days (Sun-Thu)", value=True,
        help="If a task starts or ends on Friday/Saturday, the bar is moved to the nearest working day.",
    )
with f4:
    zoom = st.select_slider("Zoom (px/day)", options=[8, 12, 16, 20, 26, 32], value=16)

today = pd.Timestamp.today().normalize()
if hide_done:
    df = df[df["End Date"] >= today]

if df.empty:
    st.info("No tasks to display with the current filters.")
    st.stop()

# ---- Working days (Sun-Thu) ----
plot_start, plot_end, work_days, weekend_flag = [], [], [], []
for s, e, is_m in zip(df["Start Date"], df["End Date"], df["IsMilestone"]):
    s_d, e_d = s.date(), e.date()
    wd = int(np.busday_count(s_d, e_d + datetime.timedelta(days=1), weekmask=NP_WEEKMASK))
    s_fix = pd.Timestamp(np.busday_offset(s_d, 0, roll="forward", weekmask=NP_WEEKMASK))
    e_fix = pd.Timestamp(np.busday_offset(e_d, 0, roll="backward", weekmask=NP_WEEKMASK))
    on_weekend = (s.dayofweek in (4, 5)) or (e.dayofweek in (4, 5))

    if snap and s_fix <= e_fix:
        plot_start.append(s_fix)
        plot_end.append(e_fix)
    elif snap and is_m and s_fix > e_fix:
        plot_start.append(s_fix)
        plot_end.append(s_fix)
    else:
        plot_start.append(s)
        plot_end.append(e)

    work_days.append(wd)
    weekend_flag.append(on_weekend)

df["Start"] = plot_start
df["End"] = plot_end
df["EndPlus"] = df["End"] + pd.Timedelta(days=1)
df["WorkDays"] = work_days
df["CalendarDays"] = (df["End Date"] - df["Start Date"]).dt.days + 1
df["OnWeekend"] = weekend_flag

code = df[code_col].astype(str) if code_col else pd.Series([""] * len(df), index=df.index)
task = df[task_col].astype(str) if task_col else pd.Series(["Task"] * len(df), index=df.index)
df["Task"] = (code + " · " + task).str.strip(" ·")
df["Stage"] = df[stage_col].astype(str) if stage_col else "-"
df["Disc"] = df[disc_col].astype(str) if disc_col else "-"
df["Resp"] = df[resp_col].astype(str) if resp_col else "-"

df = df.sort_values(["Start", "End"]).reset_index(drop=True)

# ---- Summary metrics ----
m1, m2, m3, m4 = st.columns(4)
m1.metric("Tasks", len(df))
m2.metric("First start", f"{df['Start Date'].min():%d-%b-%Y}")
m3.metric("Last end", f"{df['End Date'].max():%d-%b-%Y}")
m4.metric(
    "Working days (Sun-Thu)",
    int(np.busday_count(df["Start Date"].min().date(),
                        df["End Date"].max().date() + datetime.timedelta(days=1),
                        weekmask=NP_WEEKMASK)),
)
n_wk = int(df["OnWeekend"].sum())
if n_wk:
    st.caption(
        f"ℹ️ {n_wk} task(s) have a start or end date on Friday/Saturday (weekend). "
        + ("Their bars were snapped to the nearest working day." if snap else "Bars shown with original dates.")
    )

# ---- Interactive Gantt Chart ----
df["Code"] = code
html_doc, comp_h = build_wbs_html(df, zoom, today)
components.html(html_doc, height=comp_h, scrolling=False)
st.caption(
    "Left: WBS table (Start / End / Department). Right: timeline - grey bands = weekend (Friday & Saturday), "
    "diamonds = Milestones, black bars = stage summary, red dashed line = today. "
    "Working days are counted Sunday to Thursday only."
)

# ---- PDF export ----
try:
    pdf_bytes = build_wbs_pdf(df, today, meta=meta_info)
    clean_pname = "".join(ch for ch in str(meta_info.get("project name")) if ch.isalnum() or ch in (" ", "_", "-")).strip()
    st.download_button(
        "🖨️ Download PDF (A3 - full schedule on one page)",
        data=pdf_bytes,
        file_name=f"{clean_pname}_{today:%Y%m%d}.pdf",
        mime="application/pdf",
    )
except ImportError:
    st.info("PDF export requires the 'reportlab' package. Add `reportlab` to requirements.txt.")

with st.expander("📋 Data table"):
    show = pd.DataFrame({
        "WBS Code": df["Code"],
        "Type": np.where(df["IsMilestone"], "Milestone", "Task"),
        "Stage": df["Stage"],
        "Task": task,
        "Department": df["Disc"],
        "Responsible": df["Resp"],
        "Start": df["Start Date"].dt.strftime("%a %d-%b-%Y"),
        "End": df["End Date"].dt.strftime("%a %d-%b-%Y"),
        "Working days (Sun-Thu)": df["WorkDays"],
        "Calendar days": df["CalendarDays"],
    })
    st.dataframe(show, use_container_width=True, hide_index=True)

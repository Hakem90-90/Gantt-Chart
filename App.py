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
    TITLE_H = 38 if dates_part else 30
    HDR_H = 30
    # زيادة ارتفاع التذييل لحساب مساحة الملاحظة أسفل الجدول
    FOOT_H = 30 if p_note else 16
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

    curr_y = PH - M - 27
    if dates_part:
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(hexc("#2b4360"))
        c.drawString(M, curr_y, fit(dates_part, "Helvetica-Bold", 8, PW - 2 * M - 140))
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

    # ---- Bottom / Footer Note Area ----
    if p_note:
        footer_y = body_bot - 16
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(hexc("#2b4360"))
        c.drawString(M, footer_y, "Note*:")
        
        c.setFont("Helvetica", 7.5)
        c.setFillColor(hexc("#374151"))
        note_prefix_w = stringWidth("Note*: ", "Helvetica-Bold", 7.5)
        max_note_w = (LW + TL_W) - note_prefix_w - 4
        c.drawString(M + note_prefix_w, footer_y, fit(p_note, "Helvetica", 7.5, max_note_w))

    c.showPage()
    c.save()
    return buf.getvalue()

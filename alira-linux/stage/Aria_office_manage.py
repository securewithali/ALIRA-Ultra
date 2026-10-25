# -*- coding: utf-8 -*-
"""
TITAN Office & File Manager v1.0
================================
Features:
  ✅ Excel — create, edit, navigate rows/cols, salary calc, SUM/AVG
  ✅ MS Word — create, type text, click buttons, format
  ✅ PowerPoint — auto 7-8 slide deck with full content
  ✅ File Management — copy, paste, move, delete, extract, merge, read folder
  ✅ PDF Reader — read PDF content (any open PDF)
  ✅ Real-time Location Awareness — current folder, file, active window auto-detect
  ✅ Windows Management — list, focus, move, resize, snap windows
"""

import os, sys, asyncio, subprocess, time, shutil, json, ctypes, threading
import datetime, math, re, glob, tempfile
from pathlib import Path

# ── Optional imports ──────────────────────────────────────────
try:
    import win32com.client
    import win32gui, win32con, win32api, win32process
    import pythoncom
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import pyautogui
    import pyperclip
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter, column_index_from_string
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    from pptx import Presentation
    from pptx.util import Inches as PInches, Pt as PPt, Emu
    from pptx.dml.color import RGBColor as PRGBColor
    from pptx.enum.text import PP_ALIGN
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import pygetwindow as gw
    HAS_GW = True
except ImportError:
    HAS_GW = False

# ── Directories ───────────────────────────────────────────────
HOME = Path.home()
EXCEL_DIR = HOME / "Documents" / "TITAN_Excel"
WORD_DIR  = HOME / "Documents" / "TITAN_Word"
PPT_DIR   = HOME / "Documents" / "TITAN_PPT"
for d in [EXCEL_DIR, WORD_DIR, PPT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Location State ─────────────────────────────────────────────
_location_state = {
    "active_app":    "",
    "active_file":   "",
    "active_folder": "",
    "active_window": "",
    "excel_cell":    "A1",
    "excel_sheet":   "Sheet1",
    "word_page":     1,
    "last_update":   0,
}

def _set_clipboard(text: str):
    """Direct Win32 clipboard — IME bypass"""
    if not HAS_WIN32:
        try: pyperclip.copy(text)
        except: pass
        return
    try:
        import ctypes
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE  = 0x0002
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        encoded = (text + '\0').encode('utf-16-le')
        h = k32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        p = k32.GlobalLock(h)
        ctypes.memmove(p, encoded, len(encoded))
        k32.GlobalUnlock(h)
        u32.OpenClipboard(None)
        u32.EmptyClipboard()
        u32.SetClipboardData(CF_UNICODETEXT, h)
        u32.CloseClipboard()
    except:
        try: pyperclip.copy(text)
        except: pass


# ══════════════════════════════════════════════════════════════
# REAL-TIME LOCATION AWARENESS
# ══════════════════════════════════════════════════════════════

def _get_active_window_info() -> dict:
    """Active window ka title, file path, folder detect karo"""
    info = {"title": "", "file": "", "folder": "", "app": ""}
    if not HAS_WIN32:
        return info
    try:
        hwnd  = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        info["title"] = title

        # Process name nikalo
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid) if HAS_PSUTIL else None
            if proc:
                info["app"] = proc.name().lower()
                # Agar Excel/Word/PPT open files hain toh unka path bhi mil sakta hai
                for f in proc.open_files():
                    ext = Path(f.path).suffix.lower()
                    if ext in ('.xlsx','.xls','.xlsm','.docx','.doc','.pptx','.ppt','.pdf','.txt'):
                        info["file"]   = f.path
                        info["folder"] = str(Path(f.path).parent)
                        break
        except: pass

        # Title se file name extract karo (e.g. "Budget.xlsx - Excel")
        if not info["file"]:
            for sep in [" - Microsoft Excel", " - Excel", " - Microsoft Word", " - Word",
                        " - PowerPoint", " - Microsoft PowerPoint", " - Adobe Acrobat",
                        " - Notepad", " - Notepad++"]:
                if sep in title:
                    fname = title.split(sep)[0].strip()
                    if fname and not fname.startswith("Microsoft"):
                        info["file"] = fname
                    break

        # Active Explorer window ka folder detect karo
        if not info["folder"] and HAS_WIN32:
            try:
                pythoncom.CoInitialize()
                shell = win32com.client.Dispatch("Shell.Application")
                for w in shell.Windows():
                    try:
                        loc = w.LocationURL
                        if loc and loc.startswith("file:///"):
                            folder = loc.replace("file:///","").replace("/","\\")
                            info["folder"] = folder
                            break
                    except: pass
            except: pass

    except: pass
    return info


async def get_current_location() -> str:
    """
    User abhi kahan hai — automatically detect karo.
    Active window, file, folder, app sab batao.
    Kuch poochne ki zaroorat nahi.
    """
    def _detect():
        wi = _get_active_window_info()
        _location_state["active_window"] = wi.get("title", "")
        _location_state["active_app"]    = wi.get("app", "")
        _location_state["active_file"]   = wi.get("file", "")
        _location_state["active_folder"] = wi.get("folder", "")
        _location_state["last_update"]   = time.time()

        lines = [f"📍 Current Location:"]
        if wi["title"]:   lines.append(f"  🪟 Active Window: {wi['title']}")
        if wi["app"]:     lines.append(f"  💻 Application:   {wi['app']}")
        if wi["file"]:    lines.append(f"  📄 File:          {wi['file']}")
        if wi["folder"]:  lines.append(f"  📁 Folder:        {wi['folder']}")

        # Excel cell position
        if "excel" in wi.get("app","") or "excel" in wi.get("title","").lower():
            cell = _get_excel_active_cell()
            if cell:
                _location_state["excel_cell"] = cell
                lines.append(f"  📊 Excel Cell:    {cell}")

        if len(lines) == 1:
            lines.append("  ℹ️  Koi active file/folder nahi mila")
        return "\n".join(lines)

    return await asyncio.to_thread(_detect)


def _get_excel_active_cell() -> str:
    """Excel mein currently selected cell ka address (e.g. B5)"""
    if not HAS_WIN32:
        return _location_state.get("excel_cell", "A1")
    try:
        pythoncom.CoInitialize()
        xl = win32com.client.GetActiveObject("Excel.Application")
        cell = xl.ActiveCell
        addr = cell.Address.replace("$", "")
        sheet = xl.ActiveSheet.Name
        _location_state["excel_cell"]  = addr
        _location_state["excel_sheet"] = sheet
        return f"{sheet}!{addr}"
    except:
        return _location_state.get("excel_cell", "A1")


async def watch_location_realtime(interval_seconds: int = 5) -> str:
    """Background mein continuously location track karo"""
    async def _loop():
        while True:
            wi = _get_active_window_info()
            _location_state["active_window"] = wi.get("title","")
            _location_state["active_app"]    = wi.get("app","")
            _location_state["active_file"]   = wi.get("file","")
            _location_state["active_folder"] = wi.get("folder","")
            _location_state["last_update"]   = time.time()
            if "excel" in wi.get("app","").lower():
                cell = await asyncio.to_thread(_get_excel_active_cell)
            await asyncio.sleep(interval_seconds)
    asyncio.create_task(_loop())
    return f"✅ Location tracking shuru hua — har {interval_seconds}s mein update"


# ══════════════════════════════════════════════════════════════
# EXCEL TOOLS
# ══════════════════════════════════════════════════════════════

def _excel_app():
    """Running Excel instance ya naya open karo"""
    if not HAS_WIN32:
        return None
    try:
        pythoncom.CoInitialize()
        try:
            return win32com.client.GetActiveObject("Excel.Application")
        except:
            xl = win32com.client.Dispatch("Excel.Application")
            xl.Visible = True
            return xl
    except:
        return None


async def excel_create_file(filename: str = "", sheet_name: str = "Sheet1") -> str:
    """Naya Excel file banao"""
    if not HAS_OPENPYXL:
        return "❌ pip install openpyxl"
    def _create():
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename if filename else f"TITAN_Excel_{ts}.xlsx"
        if not fname.endswith(".xlsx"): fname += ".xlsx"
        path = EXCEL_DIR / fname
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name
        wb.save(str(path))
        os.startfile(str(path))
        _location_state["active_file"] = str(path)
        return f"✅ Excel file bani: {path}"
    return await asyncio.to_thread(_create)


async def excel_navigate(cell: str = "", row: int = 0, col: int = 0,
                          direction: str = "") -> str:
    """
    Excel mein navigate karo.
    cell: 'B5' format
    direction: up/down/left/right/home/end
    """
    def _nav():
        xl = _excel_app()
        if not xl:
            return "❌ Excel open nahi hai"
        try:
            wb = xl.ActiveWorkbook
            ws = xl.ActiveSheet

            if cell:
                ws.Range(cell).Select()
                _location_state["excel_cell"] = cell
                return f"✅ Cell {cell} pe gaye"

            if row > 0 and col > 0:
                ws.Cells(row, col).Select()
                addr = ws.Cells(row, col).Address.replace("$","")
                _location_state["excel_cell"] = addr
                return f"✅ Row {row}, Col {col} ({addr}) pe gaye"

            if direction:
                d_map = {
                    "up":    win32con.VK_UP,
                    "down":  win32con.VK_DOWN,
                    "left":  win32con.VK_LEFT,
                    "right": win32con.VK_RIGHT,
                    "home":  win32con.VK_HOME,
                    "end":   win32con.VK_END,
                }
                key = d_map.get(direction.lower())
                if key:
                    pyautogui.press(direction.lower())
                    # Update cell
                    new_cell = xl.ActiveCell.Address.replace("$","")
                    _location_state["excel_cell"] = new_cell
                    return f"✅ {direction} → {new_cell}"
            return "❌ cell/row+col/direction mein se koi ek do"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_nav)


async def excel_get_position() -> str:
    """Excel mein abhi kahan hain — row, col, cell address"""
    def _pos():
        xl = _excel_app()
        if not xl:
            return f"📊 Last known: {_location_state.get('excel_cell','?')}"
        try:
            c     = xl.ActiveCell
            addr  = c.Address.replace("$","")
            row   = c.Row
            col   = c.Column
            sheet = xl.ActiveSheet.Name
            total_rows = xl.ActiveSheet.UsedRange.Rows.Count
            total_cols = xl.ActiveSheet.UsedRange.Columns.Count
            _location_state["excel_cell"]  = addr
            _location_state["excel_sheet"] = sheet
            return (f"📊 Excel Position:\n"
                    f"  Sheet: {sheet}\n"
                    f"  Cell: {addr}  (Row {row}, Col {col})\n"
                    f"  Used Range: {total_rows} rows × {total_cols} cols")
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_pos)


async def excel_write_cell(value: str, cell: str = "", row: int = 0,
                            col: int = 0, next_row: bool = False) -> str:
    """Excel cell mein value likhо"""
    def _write():
        xl = _excel_app()
        if not xl:
            return "❌ Excel open nahi hai"
        try:
            ws = xl.ActiveSheet
            if cell:
                ws.Range(cell).Value = value
                addr = cell
            elif row > 0 and col > 0:
                ws.Cells(row, col).Value = value
                addr = ws.Cells(row, col).Address.replace("$","")
            else:
                c    = xl.ActiveCell
                c.Value = value
                addr = c.Address.replace("$","")
                if next_row:
                    xl.ActiveCell.Offset(1, 0).Select()
                else:
                    xl.ActiveCell.Offset(0, 1).Select()
            _location_state["excel_cell"] = addr
            xl.ActiveWorkbook.Save()
            return f"✅ {addr} = '{value}'"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_write)


async def excel_add_headers(headers: list, row: int = 1, start_col: int = 1,
                             bold: bool = True, bg_color: str = "4472C4") -> str:
    """Excel mein headers row banao"""
    def _headers():
        xl = _excel_app()
        if not xl:
            return "❌ Excel open nahi hai"
        try:
            ws = xl.ActiveSheet
            for i, h in enumerate(headers, start_col):
                c = ws.Cells(row, i)
                c.Value = h
                if bold:
                    c.Font.Bold = True
                    c.Font.Color = 0xFFFFFF  # White text
                    c.Interior.Color = int(bg_color, 16)  # Blue bg
                c.ColumnWidth = max(15, len(str(h)) + 4)
                c.HorizontalAlignment = -4108  # Center
            xl.ActiveWorkbook.Save()
            return f"✅ {len(headers)} headers add ho gaye: {', '.join(headers)}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_headers)


async def excel_add_data_row(data: list, row: int = 0) -> str:
    """Excel mein data row add karo. row=0 means next empty row"""
    def _add():
        xl = _excel_app()
        if not xl:
            return "❌ Excel open nahi hai"
        try:
            ws = xl.ActiveSheet
            if row == 0:
                # Next empty row find karo
                r = ws.UsedRange.Rows.Count + 1
                if r < 2: r = 2
            else:
                r = row
            for i, val in enumerate(data, 1):
                ws.Cells(r, i).Value = val
            xl.ActiveWorkbook.Save()
            return f"✅ Row {r} mein data add ho gaya: {data}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_add)


async def excel_formula(cell: str, formula: str) -> str:
    """Excel cell mein formula daalo (SUM, AVERAGE, etc.)"""
    def _formula():
        xl = _excel_app()
        if not xl:
            return "❌ Excel open nahi hai"
        try:
            ws = xl.ActiveSheet
            ws.Range(cell).Formula = formula
            result = ws.Range(cell).Value
            xl.ActiveWorkbook.Save()
            return f"✅ {cell} = {formula} → {result}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_formula)


async def excel_calculate(operation: str, range_addr: str, result_cell: str = "") -> str:
    """
    SUM, AVERAGE, COUNT, MAX, MIN calculate karo
    operation: sum/average/count/max/min
    range_addr: e.g. 'B2:B20'
    """
    op_map = {
        "sum":     "SUM",
        "average": "AVERAGE",
        "avg":     "AVERAGE",
        "count":   "COUNT",
        "max":     "MAX",
        "min":     "MIN",
    }
    op = op_map.get(operation.lower(), operation.upper())
    formula = f"={op}({range_addr})"

    def _calc():
        xl = _excel_app()
        if not xl:
            return "❌ Excel open nahi hai"
        try:
            ws = xl.ActiveSheet
            if result_cell:
                ws.Range(result_cell).Formula = formula
                val = ws.Range(result_cell).Value
                xl.ActiveWorkbook.Save()
                return f"✅ {result_cell} = {formula} → {val}"
            else:
                # Next empty cell mein daalo
                last_row = ws.UsedRange.Rows.Count
                last_col = ws.UsedRange.Columns.Count
                r_cell = ws.Cells(last_row + 2, 1)
                r_cell.Value = f"{op}:"
                ws.Cells(last_row + 2, 2).Formula = formula
                val = ws.Cells(last_row + 2, 2).Value
                xl.ActiveWorkbook.Save()
                return f"✅ {op}({range_addr}) = {val}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_calc)


async def excel_create_salary_sheet(
    workers: list,
    month: str = "",
    company_name: str = "Company"
) -> str:
    """
    Employee salary sheet banao with complete details.
    workers: [{"name":"Ali","join_date":"2023-01-15","leaves":2,"basic":25000}, ...]
    month: "January 2025"
    Shows: earnings, months worked, attendance, absents
    """
    if not HAS_OPENPYXL:
        return "❌ pip install openpyxl"

    def _salary():
        month_str = month or datetime.datetime.now().strftime("%B %Y")
        ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"Salary_{company_name}_{month_str.replace(' ','_')}_{ts}.xlsx"
        path  = EXCEL_DIR / fname

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Salary {month_str}"

        # ── Styles ─────────────────────────────────────
        header_fill = PatternFill("solid", fgColor="1F4E79")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        title_font  = Font(bold=True, size=14, color="1F4E79")
        sub_font    = Font(bold=True, size=11, color="2E75B6")
        center_align = Alignment(horizontal="center", vertical="center")
        thin_border  = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

        # ── Title ──────────────────────────────────────
        ws.merge_cells("A1:L1")
        ws["A1"] = f"{company_name} — Monthly Salary Sheet"
        ws["A1"].font   = title_font
        ws["A1"].alignment = center_align

        ws.merge_cells("A2:L2")
        ws["A2"] = f"Month: {month_str}"
        ws["A2"].font      = sub_font
        ws["A2"].alignment = center_align
        ws.row_dimensions[1].height = 30
        ws.row_dimensions[2].height = 20

        # ── Headers ────────────────────────────────────
        headers = [
            "S.No", "Employee Name", "Joining Date", "Months Worked",
            "Working Days", "Leaves Taken", "Present Days", "Absent Days",
            "Basic Salary (Rs)", "Per Day Salary (Rs)", "Leave Deduction (Rs)",
            "HRA (Rs)", "Bonus (Rs)", "Net Salary (Rs)"
        ]
        col_widths = [6, 20, 14, 14, 13, 13, 13, 13, 17, 17, 18, 12, 12, 15]

        for i, (h, w) in enumerate(zip(headers, col_widths), 1):
            c = ws.cell(row=3, column=i, value=h)
            c.font      = header_font
            c.fill      = header_fill
            c.alignment = center_align
            c.border    = thin_border
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[3].height = 25

        # ── Working days in month ──────────────────────
        try:
            mo = datetime.datetime.strptime(month_str, "%B %Y")
            if mo.month == 12:
                nxt = datetime.datetime(mo.year+1,1,1)
            else:
                nxt = datetime.datetime(mo.year, mo.month+1, 1)
            total_days = (nxt - datetime.datetime(mo.year, mo.month, 1)).days
            working_days = total_days - 8  # ~8 Sundays
        except:
            working_days = 26

        # ── Data rows ─────────────────────────────────
        alt_fill = PatternFill("solid", fgColor="EBF3FB")
        for idx, w in enumerate(workers, 1):
            r   = idx + 3
            fill = alt_fill if idx % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")

            name       = w.get("name", f"Employee {idx}")
            join_date  = w.get("join_date", "")
            leaves     = int(w.get("leaves", 0))
            basic      = float(w.get("basic", 0))
            hra_pct    = float(w.get("hra_pct", 0.20))   # 20% default
            bonus      = float(w.get("bonus", 0))

            # Calculate months worked
            months_worked = 1  # Default current month
            if join_date:
                try:
                    jd = datetime.datetime.strptime(join_date, "%Y-%m-%d")
                    current_date = datetime.datetime.now()
                    months = (current_date.year - jd.year) * 12 + (current_date.month - jd.month) + 1
                    months_worked = max(1, months)
                except:
                    months_worked = 1

            present    = max(0, working_days - leaves)
            absent     = leaves  # Absent days = leaves taken
            per_day    = basic / working_days if working_days else 0
            deduction  = per_day * leaves
            hra        = basic * hra_pct
            net        = basic - deduction + hra + bonus

            row_data = [
                idx, name, join_date, months_worked, working_days, leaves, present, absent,
                round(basic, 2), round(per_day, 2), round(deduction, 2),
                round(hra, 2), round(bonus, 2), round(net, 2)
            ]
            for ci, val in enumerate(row_data, 1):
                c = ws.cell(row=r, column=ci, value=val)
                c.border    = thin_border
                c.alignment = center_align
                c.fill      = fill
                if ci in (9, 10, 11, 12, 13, 14):
                    c.number_format = '#,##0.00'

        # ── Totals row ────────────────────────────────
        total_row = len(workers) + 4
        ws.cell(total_row, 1, "TOTAL").font = Font(bold=True)
        ws.cell(total_row, 2, "").font = Font(bold=True)
        total_fill = PatternFill("solid", fgColor="BDD7EE")
        for ci in range(1, len(headers)+1):
            c = ws.cell(row=total_row, column=ci)
            c.fill   = total_fill
            c.border = thin_border
            c.alignment = center_align
            if ci >= 9:
                col_letter = get_column_letter(ci)
                start = 4; end = total_row - 1
                c.value  = f"=SUM({col_letter}{start}:{col_letter}{end})"
                c.number_format = '#,##0.00'
                c.font   = Font(bold=True)

        # ── Summary box ───────────────────────────────
        sr = total_row + 2
        ws.cell(sr, 1, "Summary").font = Font(bold=True, size=12, color="1F4E79")
        ws.cell(sr+1, 1, f"Total Employees:").font = Font(bold=True)
        ws.cell(sr+1, 2, len(workers))
        ws.cell(sr+2, 1, f"Month:").font = Font(bold=True)
        ws.cell(sr+2, 2, month_str)
        ws.cell(sr+3, 1, f"Working Days:").font = Font(bold=True)
        ws.cell(sr+3, 2, working_days)
        ws.cell(sr+4, 1, "Generated by TITAN").font = Font(italic=True, color="888888")

        # ── Freeze top rows ───────────────────────────
        ws.freeze_panes = "A4"

        wb.save(str(path))
        os.startfile(str(path))
        _location_state["active_file"] = str(path)
        return f"✅ Salary sheet bani: {path}\n📊 {len(workers)} employees | {working_days} working days"

    return await asyncio.to_thread(_salary)


async def excel_read_cell(cell: str = "") -> str:
    """Excel cell ki value padho"""
    def _read():
        xl = _excel_app()
        if not xl:
            return "❌ Excel open nahi hai"
        try:
            ws = xl.ActiveSheet
            if cell:
                val = ws.Range(cell).Value
                return f"📊 {cell} = {val}"
            else:
                c   = xl.ActiveCell
                addr = c.Address.replace("$","")
                val  = c.Value
                return f"📊 Current ({addr}) = {val}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_read)


async def excel_select_range(start_cell: str, end_cell: str) -> str:
    """Excel mein range select karo"""
    def _select():
        xl = _excel_app()
        if not xl: return "❌ Excel open nahi hai"
        try:
            rng = f"{start_cell}:{end_cell}"
            xl.ActiveSheet.Range(rng).Select()
            return f"✅ Range {rng} selected"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_select)


async def excel_auto_fit() -> str:
    """Excel columns aur rows ko auto-fit karo"""
    def _fit():
        xl = _excel_app()
        if not xl: return "❌ Excel open nahi hai"
        try:
            xl.ActiveSheet.Columns.AutoFit()
            xl.ActiveSheet.Rows.AutoFit()
            return "✅ AutoFit ho gaya"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_fit)


async def excel_add_chart(chart_type: str = "bar", data_range: str = "",
                           title: str = "Chart") -> str:
    """Excel mein chart add karo"""
    def _chart():
        xl = _excel_app()
        if not xl: return "❌ Excel open nahi hai"
        try:
            ws   = xl.ActiveSheet
            wb   = xl.ActiveWorkbook
            rng  = ws.Range(data_range) if data_range else ws.UsedRange
            chart_obj = ws.ChartObjects().Add(100, 50, 375, 225)
            chart     = chart_obj.Chart
            chart.SetSourceData(rng)
            chart_types = {
                "bar":   -4100,   "column": 51,  "line":   4,
                "pie":   5,        "area":   1,   "scatter":74
            }
            chart.ChartType = chart_types.get(chart_type.lower(), 51)
            chart.HasTitle   = True
            chart.ChartTitle.Text = title
            wb.Save()
            return f"✅ {chart_type} chart add ho gaya: '{title}'"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_chart)


# ══════════════════════════════════════════════════════════════
# MS WORD TOOLS
# ══════════════════════════════════════════════════════════════

def _word_app():
    if not HAS_WIN32: return None
    try:
        pythoncom.CoInitialize()
        try:
            return win32com.client.GetActiveObject("Word.Application")
        except:
            app = win32com.client.Dispatch("Word.Application")
            app.Visible = True
            return app
    except:
        return None


async def word_create_file(filename: str = "", template: str = "") -> str:
    """Naya Word document banao"""
    if not HAS_DOCX:
        return "❌ pip install python-docx"
    def _create():
        ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filename if filename else f"TITAN_Doc_{ts}.docx"
        if not fname.endswith(".docx"): fname += ".docx"
        path  = WORD_DIR / fname
        doc   = Document()
        # Default styles
        style = doc.styles['Normal']
        style.font.name = 'Calibri'
        style.font.size = Pt(11)
        doc.save(str(path))
        os.startfile(str(path))
        _location_state["active_file"] = str(path)
        return f"✅ Word document bana: {path}"
    return await asyncio.to_thread(_create)


async def word_type_text(text: str, heading_level: int = 0,
                          bold: bool = False, italic: bool = False,
                          font_size: int = 11, new_line: bool = True) -> str:
    """
    Active Word document mein text type karo.
    heading_level: 0=normal, 1=Heading1, 2=Heading2, 3=Heading3
    """
    def _type():
        app = _word_app()
        if not app:
            # Fallback: active window mein type karo
            if HAS_GUI:
                _set_clipboard(text)
                pyautogui.hotkey('ctrl','v')
                if new_line:
                    pyautogui.press('enter')
                return f"✅ Text type kiya (clipboard method)"
            return "❌ Word open nahi hai"
        try:
            doc = app.ActiveDocument
            sel = app.Selection

            if heading_level > 0:
                sel.Style = doc.Styles(f"Heading {heading_level}")
                sel.TypeText(text)
                sel.TypeParagraph()
            else:
                if bold:   sel.Font.Bold = True
                if italic: sel.Font.Italic = True
                sel.Font.Size = font_size
                sel.TypeText(text)
                if new_line: sel.TypeParagraph()
                sel.Font.Bold   = False
                sel.Font.Italic = False
                sel.Font.Size   = 11   # reset
            doc.Save()
            return f"✅ Text add ho gaya: '{text[:50]}...'" if len(text)>50 else f"✅ '{text}' add ho gaya"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_type)


async def word_click_button(button_name: str) -> str:
    """
    Word ka ribbon button click karo.
    button_name: bold, italic, underline, align_left, align_center, align_right,
                 justify, bullet_list, numbered_list, insert_table, save,
                 undo, redo, find, replace, print, font_bigger, font_smaller,
                 heading1, heading2, heading3, page_break, spell_check
    """
    buttons = {
        "bold":          lambda: pyautogui.hotkey('ctrl','b'),
        "italic":        lambda: pyautogui.hotkey('ctrl','i'),
        "underline":     lambda: pyautogui.hotkey('ctrl','u'),
        "align_left":    lambda: pyautogui.hotkey('ctrl','l'),
        "align_center":  lambda: pyautogui.hotkey('ctrl','e'),
        "align_right":   lambda: pyautogui.hotkey('ctrl','r'),
        "justify":       lambda: pyautogui.hotkey('ctrl','j'),
        "save":          lambda: pyautogui.hotkey('ctrl','s'),
        "undo":          lambda: pyautogui.hotkey('ctrl','z'),
        "redo":          lambda: pyautogui.hotkey('ctrl','y'),
        "find":          lambda: pyautogui.hotkey('ctrl','f'),
        "replace":       lambda: pyautogui.hotkey('ctrl','h'),
        "print":         lambda: pyautogui.hotkey('ctrl','p'),
        "select_all":    lambda: pyautogui.hotkey('ctrl','a'),
        "copy":          lambda: pyautogui.hotkey('ctrl','c'),
        "paste":         lambda: pyautogui.hotkey('ctrl','v'),
        "cut":           lambda: pyautogui.hotkey('ctrl','x'),
        "page_break":    lambda: pyautogui.hotkey('ctrl','enter'),
        "new_line":      lambda: pyautogui.press('enter'),
        "tab":           lambda: pyautogui.press('tab'),
        "font_bigger":   lambda: pyautogui.hotkey('ctrl','shift','.'),
        "font_smaller":  lambda: pyautogui.hotkey('ctrl','shift',','),
        "heading1":      lambda: pyautogui.hotkey('ctrl','alt','1'),
        "heading2":      lambda: pyautogui.hotkey('ctrl','alt','2'),
        "heading3":      lambda: pyautogui.hotkey('ctrl','alt','3'),
        "normal_style":  lambda: pyautogui.hotkey('ctrl','shift','n'),
        "spell_check":   lambda: pyautogui.press('f7'),
        "bullet_list":   lambda: _word_bullet(),
        "numbered_list": lambda: _word_numbered(),
        "insert_table":  lambda: pyautogui.hotkey('ctrl','f5'),
        "zoom_in":       lambda: pyautogui.hotkey('ctrl','='),
        "zoom_out":      lambda: pyautogui.hotkey('ctrl','-'),
    }

    def _word_bullet():
        app = _word_app()
        if app:
            sel = app.Selection
            sel.Range.ListFormat.ApplyBulletDefault()
    def _word_numbered():
        app = _word_app()
        if app:
            sel = app.Selection
            sel.Range.ListFormat.ApplyNumberDefault()

    def _click():
        if not HAS_GUI:
            return "❌ pyautogui install karo"
        fn = buttons.get(button_name.lower())
        if fn:
            fn()
            return f"✅ '{button_name}' button click hua"
        return f"❌ Unknown button: {button_name}. Available: {', '.join(buttons.keys())}"
    return await asyncio.to_thread(_click)


async def word_insert_table(rows: int, cols: int, data: list = None) -> str:
    """Word mein table insert karo"""
    def _table():
        app = _word_app()
        if not app:
            return "❌ Word open nahi hai"
        try:
            doc = app.ActiveDocument
            sel = app.Selection
            tbl = sel.Tables.Add(sel.Range, rows, cols)
            tbl.Borders.Enable = True
            # Header row style
            for c in range(1, cols+1):
                cell = tbl.Cell(1, c)
                cell.Range.Font.Bold = True
                cell.Shading.BackgroundPatternColor = 0x4472C4
                cell.Range.Font.Color = 0xFFFFFF
            # Fill data if provided
            if data:
                for ri, row_data in enumerate(data[:rows], 1):
                    for ci, val in enumerate(row_data[:cols], 1):
                        tbl.Cell(ri, ci).Range.Text = str(val)
            doc.Save()
            return f"✅ {rows}×{cols} table insert ho gaya"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_table)


async def word_format_text(text_to_find: str, bold: bool = False,
                            italic: bool = False, color: str = "",
                            size: int = 0) -> str:
    """Word mein specific text ko format karo"""
    def _format():
        app = _word_app()
        if not app: return "❌ Word open nahi hai"
        try:
            doc = app.ActiveDocument
            find = app.Selection.Find
            find.ClearFormatting()
            find.Replacement.ClearFormatting()
            find.Text = text_to_find
            find.Forward = True
            find.MatchCase = False
            if find.Execute():
                sel = app.Selection
                if bold:   sel.Font.Bold   = True
                if italic: sel.Font.Italic = True
                if size:   sel.Font.Size   = size
                if color:
                    r = int(color[0:2],16)
                    g = int(color[2:4],16)
                    b = int(color[4:6],16)
                    sel.Font.Color = r + (g<<8) + (b<<16)
                doc.Save()
                return f"✅ '{text_to_find}' format ho gaya"
            return f"❌ '{text_to_find}' nahi mila"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_format)


async def word_get_position() -> str:
    """Word mein abhi kahan hain — page, line, column"""
    def _pos():
        app = _word_app()
        if not app: return f"📄 Word position unknown"
        try:
            sel  = app.Selection
            page = sel.Information(3)    # wdActiveEndPageNumber
            line = sel.Information(10)   # wdFirstCharacterLineNumber
            col  = sel.Information(16)   # wdFirstCharacterColumnNumber
            doc  = app.ActiveDocument
            total_pages = doc.ComputeStatistics(2)  # wdStatisticPages
            _location_state["word_page"] = page
            return (f"📄 Word Position:\n"
                    f"  Page:   {page} / {total_pages}\n"
                    f"  Line:   {line}\n"
                    f"  Column: {col}")
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_pos)


# ══════════════════════════════════════════════════════════════
# POWERPOINT TOOLS
# ══════════════════════════════════════════════════════════════

async def ppt_create_presentation(
    topic: str,
    slides_content: list = None,
    title: str = "",
    theme_color: str = "1F4E79",
    num_slides: int = 7
) -> str:
    """
    Full PowerPoint presentation banao.
    slides_content: [{"title":"...", "content":"...", "bullets":["a","b"]}]
    num_slides: 7-8 slides with full content
    """
    if not HAS_PPTX:
        return "❌ pip install python-pptx"

    def _ppt():
        ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"TITAN_PPT_{topic[:30].replace(' ','_')}_{ts}.pptx"
        path  = PPT_DIR / fname

        prs  = Presentation()
        prs.slide_width  = PInches(13.33)
        prs.slide_height = PInches(7.5)

        # Color scheme
        bg_color   = PRGBColor(0x1F, 0x4E, 0x79)
        text_color = PRGBColor(0xFF, 0xFF, 0xFF)
        accent_col = PRGBColor(0x2E, 0x75, 0xB6)

        # Auto generate content if not provided
        if not slides_content:
            slides_content_gen = _auto_generate_slides(topic, num_slides)
        else:
            slides_content_gen = slides_content

        layouts = prs.slide_layouts

        for si, slide_data in enumerate(slides_content_gen):
            if si == 0:
                # Title Slide
                layout = layouts[0]
                slide  = prs.slides.add_slide(layout)
                # Background
                bg = slide.background
                fill = bg.fill
                fill.solid()
                fill.fore_color.rgb = bg_color

                # Title
                tf = slide.placeholders[0].text_frame
                tf.clear()
                p  = tf.paragraphs[0]
                p.alignment = PP_ALIGN.CENTER
                run = p.add_run()
                run.text = slide_data.get("title", topic)
                run.font.size  = PPt(44)
                run.font.bold  = True
                run.font.color.rgb = PRGBColor(0xFF, 0xFF, 0xFF)

                # Subtitle
                if len(slide.placeholders) > 1:
                    tf2 = slide.placeholders[1].text_frame
                    tf2.clear()
                    p2  = tf2.paragraphs[0]
                    p2.alignment = PP_ALIGN.CENTER
                    r2  = p2.add_run()
                    r2.text = slide_data.get("content", f"Presented by TITAN\n{datetime.date.today()}")
                    r2.font.size  = PPt(20)
                    r2.font.color.rgb = PRGBColor(0xBD, 0xD7, 0xEE)

            else:
                # Content Slide
                layout = layouts[1]
                slide  = prs.slides.add_slide(layout)

                # Background gradient effect using shape
                bg = slide.background
                bg.fill.solid()
                bg.fill.fore_color.rgb = PRGBColor(0x0D, 0x1B, 0x2A)

                # Slide title
                tf = slide.placeholders[0].text_frame
                tf.clear()
                p  = tf.paragraphs[0]
                run = p.add_run()
                run.text = slide_data.get("title", f"Slide {si+1}")
                run.font.size  = PPt(32)
                run.font.bold  = True
                run.font.color.rgb = PRGBColor(0x5B, 0x9B, 0xD5)

                # Content body
                tf2 = slide.placeholders[1].text_frame
                tf2.clear()
                tf2.word_wrap = True

                content = slide_data.get("content", "")
                bullets = slide_data.get("bullets", [])

                if content and not bullets:
                    # Convert paragraphs to bullets
                    bullets = [s.strip() for s in content.split('\n') if s.strip()]

                for bi, bullet in enumerate(bullets[:8]):
                    p2 = tf2.paragraphs[0] if bi == 0 else tf2.add_paragraph()
                    p2.level = 0
                    run2 = p2.add_run()
                    run2.text = f"• {bullet}"
                    run2.font.size  = PPt(18)
                    run2.font.color.rgb = PRGBColor(0xE0, 0xE8, 0xF0)
                    run2.font.bold  = (bi == 0)

                # Slide number
                txb = slide.shapes.add_textbox(
                    PInches(12.5), PInches(6.8), PInches(0.8), PInches(0.4))
                tf3 = txb.text_frame
                p3  = tf3.paragraphs[0]
                r3  = p3.add_run()
                r3.text = str(si + 1)
                r3.font.size  = PPt(12)
                r3.font.color.rgb = PRGBColor(0x80, 0x80, 0x80)
                p3.alignment = PP_ALIGN.RIGHT

        prs.save(str(path))
        os.startfile(str(path))
        _location_state["active_file"] = str(path)
        return f"✅ PPT bani: {path}\n📊 {len(slides_content_gen)} slides | Topic: {topic}"

    return await asyncio.to_thread(_ppt)


def _auto_generate_slides(topic: str, num: int = 7) -> list:
    """Topic ke hisab se auto slide content generate karo"""
    slides = [
        {
            "title":   topic,
            "content": f"A comprehensive presentation on {topic}\n\nPrepared by TITAN AI Assistant\n{datetime.date.today()}"
        },
        {
            "title":   "Table of Contents",
            "bullets": [
                "1. Introduction & Overview",
                "2. Key Concepts",
                "3. Main Features & Benefits",
                "4. Implementation / Process",
                "5. Case Study / Examples",
                "6. Challenges & Solutions",
                "7. Conclusion & Next Steps"
            ]
        },
        {
            "title":   f"Introduction to {topic}",
            "bullets": [
                f"{topic} ek important concept hai jo aaj ke daur mein bahut relevant hai",
                "Yeh presentation iske key aspects cover karti hai",
                "Hum iske fayde, challenges aur applications dekhenge",
                f"Understanding {topic} is essential for modern professionals",
                "Let's dive deep into this fascinating subject"
            ]
        },
        {
            "title":   "Key Concepts & Core Ideas",
            "bullets": [
                f"Fundamental principles of {topic}",
                "Core components and building blocks",
                "How the key elements work together",
                "Important terminology and definitions",
                "Theoretical framework and models"
            ]
        },
        {
            "title":   "Features & Benefits",
            "bullets": [
                f"Primary advantages of {topic}",
                "Efficiency improvements and cost savings",
                "Enhanced performance and scalability",
                "Better user experience and satisfaction",
                "Long-term strategic value"
            ]
        },
        {
            "title":   "Implementation & Process",
            "bullets": [
                "Step 1: Planning and preparation",
                "Step 2: Resource allocation",
                "Step 3: Execution and deployment",
                "Step 4: Testing and quality assurance",
                "Step 5: Monitoring and optimization"
            ]
        },
        {
            "title":   "Challenges & Solutions",
            "bullets": [
                "Common challenges faced during implementation",
                "How to overcome technical barriers",
                "Risk mitigation strategies",
                "Best practices from industry experts",
                "Lessons learned from case studies"
            ]
        },
        {
            "title":   "Conclusion & Next Steps",
            "bullets": [
                f"{topic} has transformative potential",
                "Key takeaways from this presentation",
                "Recommended action items",
                "Resources for further learning",
                "Q&A and open discussion"
            ]
        }
    ]
    return slides[:num]


async def ppt_add_slide(title: str, content: str = "",
                         bullets: list = None, slide_index: int = -1) -> str:
    """Existing PPT mein new slide add karo"""
    def _add():
        if not HAS_WIN32: return "❌ win32com chahiye"
        app = None
        try:
            pythoncom.CoInitialize()
            try:    app = win32com.client.GetActiveObject("PowerPoint.Application")
            except: return "❌ PowerPoint open nahi hai"
            prs = app.ActivePresentation
            sls = prs.Slides
            n   = sls.Count
            idx = n + 1 if slide_index < 0 else slide_index
            sl  = sls.Add(idx, 2)  # Layout 2 = Title, Content
            sl.Shapes.Title.TextFrame.TextRange.Text = title
            body = sl.Shapes(2).TextFrame.TextRange
            body.Text = ""
            items = bullets if bullets else (content.split('\n') if content else [])
            for item in items:
                if item.strip():
                    body.InsertAfter(f"• {item}\r")
            prs.Save()
            return f"✅ Slide {idx} add ho gayi: '{title}'"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_add)


# ══════════════════════════════════════════════════════════════
# FILE MANAGEMENT TOOLS
# ══════════════════════════════════════════════════════════════

async def file_copy(source: str, destination: str,
                    overwrite: bool = True) -> str:
    """File ya folder copy karo"""
    def _copy():
        src = _resolve_path(source)
        dst = _resolve_path(destination)
        if not src: return f"❌ Source nahi mila: {source}"
        try:
            if os.path.isdir(src):
                dst_full = os.path.join(dst, os.path.basename(src)) if os.path.isdir(dst) else dst
                shutil.copytree(src, dst_full, dirs_exist_ok=overwrite)
                return f"✅ Folder copy ho gaya: {dst_full}"
            else:
                os.makedirs(dst if os.path.isdir(dst) else os.path.dirname(dst), exist_ok=True)
                dst_file = os.path.join(dst, os.path.basename(src)) if os.path.isdir(dst) else dst
                shutil.copy2(src, dst_file)
                return f"✅ File copy ho gayi:\n  From: {src}\n  To:   {dst_file}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_copy)


async def file_move(source: str, destination: str) -> str:
    """File ya folder move karo"""
    def _move():
        src = _resolve_path(source)
        dst = _resolve_path(destination)
        if not src: return f"❌ Source nahi mila: {source}"
        try:
            os.makedirs(dst if os.path.isdir(dst) else os.path.dirname(dst), exist_ok=True)
            result = shutil.move(src, dst)
            return f"✅ Move ho gaya:\n  From: {src}\n  To:   {result}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_move)


async def file_delete(path: str, to_recycle: bool = True) -> str:
    """File ya folder delete karo (Recycle Bin ya permanent)"""
    def _del():
        fp = _resolve_path(path)
        if not fp: return f"❌ File nahi mili: {path}"
        try:
            if to_recycle and HAS_WIN32:
                import pythoncom
                from win32com.shell import shell as sh, shellcon
                sh.SHFileOperation((0, shellcon.FO_DELETE, fp, None,
                    shellcon.FOF_ALLOWUNDO | shellcon.FOF_NOCONFIRMATION, None, None))
                return f"✅ Recycle Bin mein bheja: {fp}"
            else:
                if os.path.isdir(fp):
                    shutil.rmtree(fp)
                    return f"✅ Folder delete ho gaya: {fp}"
                else:
                    os.remove(fp)
                    return f"✅ File delete ho gayi: {fp}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_del)


async def file_rename(path: str, new_name: str) -> str:
    """File ya folder rename karo"""
    def _ren():
        fp  = _resolve_path(path)
        if not fp: return f"❌ File nahi mili: {path}"
        parent  = os.path.dirname(fp)
        new_path = os.path.join(parent, new_name)
        try:
            os.rename(fp, new_path)
            return f"✅ Rename ho gaya: {os.path.basename(fp)} → {new_name}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_ren)


async def folder_read(folder_path: str = "", show_hidden: bool = False,
                       file_type: str = "") -> str:
    """
    Folder ka content padho — files, subfolders, sizes.
    Auto-detect current location agar path nahi diya.
    """
    def _read():
        path = _resolve_path(folder_path) if folder_path else _location_state.get("active_folder","")
        if not path:
            # Current directory
            path = os.getcwd()

        if not os.path.exists(path):
            return f"❌ Folder nahi mila: {path}"

        items = os.listdir(path)
        if not show_hidden:
            items = [i for i in items if not i.startswith('.') and
                     not (HAS_WIN32 and _is_hidden(os.path.join(path, i)))]

        if file_type:
            items = [i for i in items if i.lower().endswith(file_type.lower())]

        dirs  = [i for i in items if os.path.isdir(os.path.join(path, i))]
        files = [i for i in items if os.path.isfile(os.path.join(path, i))]
        dirs.sort(); files.sort()

        lines = [f"📁 {path}", f"   {len(dirs)} folders, {len(files)} files\n"]
        for d in dirs[:20]:
            lines.append(f"  📂 {d}/")
        for f in files[:30]:
            fp   = os.path.join(path, f)
            size = os.path.getsize(fp)
            sz   = f"{size/1024:.1f} KB" if size > 1024 else f"{size} B"
            ext  = Path(f).suffix.lower()
            icon = {"pdf":"📕","docx":"📘","xlsx":"📗","pptx":"📙","mp3":"🎵",
                    "mp4":"🎬","jpg":"🖼","png":"🖼","zip":"🗜","exe":"⚙"}.get(ext[1:],"📄")
            lines.append(f"  {icon} {f}  ({sz})")
        if len(dirs)>20: lines.append(f"  ... aur {len(dirs)-20} folders")
        if len(files)>30: lines.append(f"  ... aur {len(files)-30} files")
        return "\n".join(lines)

    return await asyncio.to_thread(_read)


def _is_hidden(path):
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
        return bool(attrs & 2)
    except:
        return False


async def file_extract(archive_path: str, destination: str = "") -> str:
    """ZIP/RAR/7z file extract karo"""
    def _extract():
        fp  = _resolve_path(archive_path)
        if not fp: return f"❌ Archive nahi mila: {archive_path}"
        ext = Path(fp).suffix.lower()
        dst = destination or str(Path(fp).parent / Path(fp).stem)
        os.makedirs(dst, exist_ok=True)
        try:
            if ext == ".zip":
                import zipfile
                with zipfile.ZipFile(fp, 'r') as zf:
                    zf.extractall(dst)
                n = len(os.listdir(dst))
                os.startfile(dst)
                return f"✅ {n} files extract ho gayi: {dst}"
            elif ext in ('.tar', '.gz', '.bz2', '.tgz'):
                import tarfile
                with tarfile.open(fp) as tf:
                    tf.extractall(dst)
                os.startfile(dst)
                return f"✅ Extract ho gaya: {dst}"
            elif ext in ('.rar', '.7z'):
                # 7-zip se extract karo
                sevenz = _find_7zip()
                if sevenz:
                    subprocess.run([sevenz, 'x', fp, f'-o{dst}', '-y'],
                                   capture_output=True)
                    os.startfile(dst)
                    return f"✅ Extract ho gaya: {dst}"
                return "❌ .rar/.7z ke liye 7-Zip install karo"
            else:
                return f"❌ Format supported nahi: {ext}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_extract)


def _find_7zip():
    paths = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ]
    for p in paths:
        if os.path.exists(p): return p
    return None


async def file_compress(source: str, output_name: str = "",
                         format: str = "zip") -> str:
    """File ya folder compress karo"""
    def _compress():
        fp  = _resolve_path(source)
        if not fp: return f"❌ Source nahi mila: {source}"
        out = output_name or f"{fp}.{format}"
        if not out.endswith(f".{format}"): out += f".{format}"
        try:
            if format == "zip":
                import zipfile
                with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
                    if os.path.isdir(fp):
                        for root, dirs, files in os.walk(fp):
                            for f in files:
                                full = os.path.join(root, f)
                                arcname = os.path.relpath(full, os.path.dirname(fp))
                                zf.write(full, arcname)
                    else:
                        zf.write(fp, os.path.basename(fp))
                size = os.path.getsize(out) / 1024
                return f"✅ Compressed: {out} ({size:.1f} KB)"
            return f"❌ Format {format} ke liye 7-Zip use karo"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_compress)


async def file_merge(files: list, output_path: str, merge_type: str = "text") -> str:
    """
    Multiple files merge karo.
    merge_type: text/pdf/excel
    files: list of file paths
    """
    def _merge():
        resolved = [_resolve_path(f) for f in files]
        missing  = [f for f, r in zip(files, resolved) if not r]
        if missing: return f"❌ Files nahi mili: {', '.join(missing)}"

        try:
            if merge_type == "text":
                with open(output_path, 'w', encoding='utf-8') as out_f:
                    for fp in resolved:
                        out_f.write(f"\n{'='*50}\n{os.path.basename(fp)}\n{'='*50}\n")
                        try:
                            with open(fp, encoding='utf-8', errors='ignore') as f:
                                out_f.write(f.read())
                        except: pass
                return f"✅ {len(resolved)} files merge ho gayi: {output_path}"

            elif merge_type == "pdf":
                if not HAS_PYPDF: return "❌ pip install pypdf"
                merger = pypdf.PdfMerger()
                for fp in resolved:
                    if fp.lower().endswith('.pdf'):
                        merger.append(fp)
                merger.write(output_path)
                merger.close()
                return f"✅ {len(resolved)} PDFs merge ho gayi: {output_path}"

            elif merge_type == "excel":
                if not HAS_OPENPYXL: return "❌ pip install openpyxl"
                out_wb = openpyxl.Workbook()
                out_wb.remove(out_wb.active)
                for fp in resolved:
                    wb   = openpyxl.load_workbook(fp, data_only=True)
                    for ws in wb.worksheets:
                        new_ws = out_wb.create_sheet(title=f"{Path(fp).stem}_{ws.title}"[:31])
                        for row in ws.iter_rows():
                            for cell in row:
                                new_ws[cell.coordinate] = cell.value
                out_wb.save(output_path)
                return f"✅ {len(resolved)} Excel files merge ho gayi: {output_path}"

            return f"❌ merge_type: text/pdf/excel"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_merge)


def _resolve_path(path: str) -> str:
    """File/folder ka full path resolve karo — relative, user-relative ya direct"""
    if not path: return ""
    # Direct path
    if os.path.exists(path): return os.path.abspath(path)
    # Home-relative
    home_path = os.path.join(str(HOME), path)
    if os.path.exists(home_path): return home_path
    # Common dirs
    for base in [HOME/"Desktop", HOME/"Downloads", HOME/"Documents",
                 HOME/"Pictures", HOME/"Videos", HOME/"Music",
                 EXCEL_DIR, WORD_DIR, PPT_DIR]:
        p = base / path
        if p.exists(): return str(p)
    # Active folder
    af = _location_state.get("active_folder","")
    if af:
        p = os.path.join(af, path)
        if os.path.exists(p): return p
    # Current dir
    p = os.path.join(os.getcwd(), path)
    if os.path.exists(p): return p
    return ""


# ══════════════════════════════════════════════════════════════
# PDF READER
# ══════════════════════════════════════════════════════════════

async def pdf_read_file(file_path: str = "", pages: str = "all") -> str:
    """
    PDF file padho.
    file_path: Path ya naam. Khali ho toh active PDF detect karta hai.
    pages: 'all', '1-5', '3' etc.
    """
    def _read():
        if not HAS_PYPDF: return "❌ pip install pypdf"

        # Auto detect
        fp = file_path
        if not fp:
            fp = _location_state.get("active_file", "")
        if not fp:
            wi = _get_active_window_info()
            fp = wi.get("file","")

        fp = _resolve_path(fp)
        if not fp or not fp.lower().endswith('.pdf'):
            # Search for recent PDFs
            downloads = HOME / "Downloads"
            pdfs = sorted(downloads.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)
            if pdfs: fp = str(pdfs[0])
            else: return "❌ Koi PDF nahi mila. Path do ya PDF kholo."

        try:
            reader = pypdf.PdfReader(fp)
            total  = len(reader.pages)

            # Page range parse karo
            if pages == "all":
                page_nums = list(range(total))
            elif '-' in pages:
                s, e = pages.split('-')
                page_nums = list(range(int(s)-1, min(int(e), total)))
            else:
                page_nums = [int(pages)-1]

            text_parts = []
            for pn in page_nums[:10]:  # Max 10 pages
                pt = reader.pages[pn].extract_text()
                if pt: text_parts.append(f"[Page {pn+1}]\n{pt.strip()}")

            full_text = "\n\n".join(text_parts)
            if not full_text.strip():
                return f"📄 {os.path.basename(fp)} ({total} pages) — Text extract nahi ho saka (scanned PDF ho sakta hai)"

            summary = full_text[:3000] + ("..." if len(full_text)>3000 else "")
            return f"📄 {os.path.basename(fp)} ({total} pages):\n\n{summary}"
        except Exception as e:
            return f"❌ Error reading PDF: {e}"
    return await asyncio.to_thread(_read)


async def pdf_get_info(file_path: str = "") -> str:
    """PDF ka metadata aur info dekho"""
    def _info():
        if not HAS_PYPDF: return "❌ pip install pypdf"
        fp = _resolve_path(file_path) if file_path else _location_state.get("active_file","")
        if not fp: return "❌ PDF path do"
        try:
            reader = pypdf.PdfReader(fp)
            meta   = reader.metadata
            size   = os.path.getsize(fp) / 1024
            lines  = [
                f"📄 {os.path.basename(fp)}",
                f"   Pages:    {len(reader.pages)}",
                f"   Size:     {size:.1f} KB",
            ]
            if meta:
                if meta.title:  lines.append(f"   Title:    {meta.title}")
                if meta.author: lines.append(f"   Author:   {meta.author}")
                if meta.subject:lines.append(f"   Subject:  {meta.subject}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_info)


# ══════════════════════════════════════════════════════════════
# WINDOWS MANAGEMENT
# ══════════════════════════════════════════════════════════════

async def window_list_all() -> str:
    """Sab open windows list karo — title, size, position"""
    def _list():
        if not HAS_WIN32: return "❌ win32gui chahiye"
        windows = []
        def _enum(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and len(title) > 2:
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        w = rect[2]-rect[0]; h = rect[3]-rect[1]
                        if w > 50 and h > 50:
                            windows.append({"hwnd":hwnd,"title":title,"w":w,"h":h,"x":rect[0],"y":rect[1]})
                    except: pass
        win32gui.EnumWindows(_enum, None)
        windows.sort(key=lambda x: x['title'])
        lines = [f"🪟 {len(windows)} Open Windows:"]
        for w in windows[:25]:
            lines.append(f"  [{w['hwnd']}] {w['title'][:50]}  ({w['w']}×{w['h']} @ {w['x']},{w['y']})")
        return "\n".join(lines)
    return await asyncio.to_thread(_list)


async def window_focus(title_or_hwnd: str) -> str:
    """Window ko focus/foreground mein lao"""
    def _focus():
        if not HAS_WIN32: return "❌ win32gui chahiye"
        hwnd = None
        try: hwnd = int(title_or_hwnd)
        except:
            def _enum(h, _):
                nonlocal hwnd
                t = win32gui.GetWindowText(h)
                if title_or_hwnd.lower() in t.lower(): hwnd = h
            win32gui.EnumWindows(_enum, None)
        if not hwnd: return f"❌ Window nahi mila: {title_or_hwnd}"
        try:
            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            title = win32gui.GetWindowText(hwnd)
            return f"✅ Focus: {title}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_focus)


async def window_resize(title: str, width: int, height: int,
                         x: int = -1, y: int = -1) -> str:
    """Window resize aur reposition karo"""
    def _resize():
        if not HAS_WIN32: return "❌ win32gui chahiye"
        hwnd = None
        def _enum(h, _):
            nonlocal hwnd
            if title.lower() in win32gui.GetWindowText(h).lower(): hwnd = h
        win32gui.EnumWindows(_enum, None)
        if not hwnd: return f"❌ Window nahi mila: {title}"
        try:
            rect = win32gui.GetWindowRect(hwnd)
            nx = x if x >= 0 else rect[0]
            ny = y if y >= 0 else rect[1]
            win32gui.MoveWindow(hwnd, nx, ny, width, height, True)
            return f"✅ {title}: {width}×{height} @ {nx},{ny}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_resize)


async def window_snap_to(title: str, position: str) -> str:
    """
    Window ko position pe snap karo.
    position: left_half, right_half, top_half, bottom_half,
              top_left, top_right, bottom_left, bottom_right, maximize, minimize
    """
    def _snap():
        if not HAS_WIN32: return "❌ win32gui chahiye"
        hwnd = None
        def _enum(h, _):
            nonlocal hwnd
            if title.lower() in win32gui.GetWindowText(h).lower(): hwnd = h
        win32gui.EnumWindows(_enum, None)
        if not hwnd: return f"❌ Window nahi mila: {title}"

        sw = win32api.GetSystemMetrics(0)
        sh = win32api.GetSystemMetrics(1)
        positions = {
            "left_half":     (0,     0,     sw//2, sh),
            "right_half":    (sw//2, 0,     sw//2, sh),
            "top_half":      (0,     0,     sw,    sh//2),
            "bottom_half":   (0,     sh//2, sw,    sh//2),
            "top_left":      (0,     0,     sw//2, sh//2),
            "top_right":     (sw//2, 0,     sw//2, sh//2),
            "bottom_left":   (0,     sh//2, sw//2, sh//2),
            "bottom_right":  (sw//2, sh//2, sw//2, sh//2),
        }
        if position == "maximize":
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return f"✅ Maximize: {title}"
        if position == "minimize":
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return f"✅ Minimize: {title}"
        if position not in positions:
            return f"❌ Position: {', '.join(positions.keys())}"
        x, y, w, h = positions[position]
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.MoveWindow(hwnd, x, y, w, h, True)
        return f"✅ {title} → {position} ({w}×{h})"
    return await asyncio.to_thread(_snap)


async def window_close(title: str, force: bool = False) -> str:
    """Window band karo"""
    def _close():
        if not HAS_WIN32: return "❌ win32gui chahiye"
        hwnd = None
        def _enum(h, _):
            nonlocal hwnd
            if title.lower() in win32gui.GetWindowText(h).lower(): hwnd = h
        win32gui.EnumWindows(_enum, None)
        if not hwnd: return f"❌ Window nahi mila: {title}"
        try:
            if force:
                win32gui.PostMessage(hwnd, win32con.WM_QUIT, 0, 0)
            else:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return f"✅ Window closed: {title}"
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_close)


async def window_get_active() -> str:
    """Abhi jo window active hai uski full info"""
    def _active():
        if not HAS_WIN32: return "❌ win32gui chahiye"
        try:
            hwnd  = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            rect  = win32gui.GetWindowRect(hwnd)
            w = rect[2]-rect[0]; h = rect[3]-rect[1]
            return (f"🪟 Active Window:\n"
                    f"  Title:  {title}\n"
                    f"  HWND:   {hwnd}\n"
                    f"  Size:   {w}×{h}\n"
                    f"  Pos:    x={rect[0]}, y={rect[1]}")
        except Exception as e:
            return f"❌ Error: {e}"
    return await asyncio.to_thread(_active)


async def window_arrange_side_by_side(title1: str, title2: str) -> str:
    """Do windows ko side-by-side arrange karo"""
    def _arrange():
        if not HAS_WIN32: return "❌ win32gui chahiye"
        hwnds = [None, None]
        titles = [title1.lower(), title2.lower()]
        def _enum(h, _):
            t = win32gui.GetWindowText(h).lower()
            for i, tl in enumerate(titles):
                if tl in t and hwnds[i] is None: hwnds[i] = h
        win32gui.EnumWindows(_enum, None)
        if not hwnds[0]: return f"❌ Window 1 nahi mila: {title1}"
        if not hwnds[1]: return f"❌ Window 2 nahi mila: {title2}"
        sw = win32api.GetSystemMetrics(0)
        sh = win32api.GetSystemMetrics(1)
        win32gui.ShowWindow(hwnds[0], win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnds[1], win32con.SW_RESTORE)
        win32gui.MoveWindow(hwnds[0], 0,     0, sw//2, sh, True)
        win32gui.MoveWindow(hwnds[1], sw//2, 0, sw//2, sh, True)
        return f"✅ Side-by-side:\n  Left:  {title1}\n  Right: {title2}"
    return await asyncio.to_thread(_arrange)


# ══════════════════════════════════════════════════════════════
# TOOL DECLARATIONS (Gemini Compatible)
# ══════════════════════════════════════════════════════════════

def _p(props: dict, req: list = []):
    return {"type": "object",
            "properties": {k: {"type": v} for k, v in props.items()},
            "required": req}

def _pa(props: dict, req: list = []):
    """Props with array support"""
    out = {}
    for k, v in props.items():
        if isinstance(v, dict): out[k] = v
        else: out[k] = {"type": v}
    return {"type":"object","properties":out,"required":req}


TITAN_OFFICE_TOOLS = [
    # ── Location Awareness ─────────────────────────────────
    {"name": "get_current_location",
     "description": "User abhi kahan hai — active window, file, folder, app automatically detect karo. Kuch poochne ki zaroorat nahi.",
     "parameters": _p({})},
    {"name": "watch_location_realtime",
     "description": "Background mein location tracking start karo — har N seconds mein update",
     "parameters": _p({"interval_seconds": "integer"})},

    # ── Excel ──────────────────────────────────────────────
    {"name": "excel_create_file",
     "description": "Naya Excel file banao aur open karo",
     "parameters": _p({"filename": "string", "sheet_name": "string"})},
    {"name": "excel_navigate",
     "description": "Excel mein navigate karo — cell address (e.g. B5), row+col, ya direction (up/down/left/right)",
     "parameters": _p({"cell":"string","row":"integer","col":"integer","direction":"string"})},
    {"name": "excel_get_position",
     "description": "Excel mein abhi kahan hain — current cell, row, column, sheet",
     "parameters": _p({})},
    {"name": "excel_write_cell",
     "description": "Excel cell mein value likho. Cell khali hone par current cell mein likhta hai aur next pe move karta hai.",
     "parameters": _p({"value":"string","cell":"string","row":"integer","col":"integer","next_row":"boolean"},["value"])},
    {"name": "excel_add_headers",
     "description": "Excel mein header row banao — bold, colored headers",
     "parameters": _pa({"headers":{"type":"array","items":{"type":"string"}},"row":"integer","start_col":"integer","bold":"boolean","bg_color":"string"},["headers"])},
    {"name": "excel_add_data_row",
     "description": "Excel mein next empty row mein data add karo",
     "parameters": _pa({"data":{"type":"array","items":{}},"row":"integer"},["data"])},
    {"name": "excel_formula",
     "description": "Excel cell mein formula daalo — =SUM(B2:B10), =AVERAGE etc.",
     "parameters": _p({"cell":"string","formula":"string"},["cell","formula"])},
    {"name": "excel_calculate",
     "description": "Excel range ka SUM/AVERAGE/COUNT/MAX/MIN nikalo",
     "parameters": _p({"operation":"string","range_addr":"string","result_cell":"string"},["operation","range_addr"])},
    {"name": "excel_create_salary_sheet",
     "description": "Company employees ki monthly salary sheet banao — working days, leaves, deductions, net salary sab calculate karta hai",
     "parameters": _pa({
         "workers": {"type":"array","items":{"type":"object"}},
         "month":        "string",
         "company_name": "string"
     },["workers"])},
    {"name": "excel_read_cell",
     "description": "Excel cell ki value padho",
     "parameters": _p({"cell":"string"})},
    {"name": "excel_select_range",
     "description": "Excel mein range select karo",
     "parameters": _p({"start_cell":"string","end_cell":"string"},["start_cell","end_cell"])},
    {"name": "excel_auto_fit",
     "description": "Excel columns aur rows autofit karo",
     "parameters": _p({})},
    {"name": "excel_add_chart",
     "description": "Excel mein chart add karo — bar/column/line/pie/area/scatter",
     "parameters": _p({"chart_type":"string","data_range":"string","title":"string"})},

    # ── MS Word ────────────────────────────────────────────
    {"name": "word_create_file",
     "description": "Naya Word document banao",
     "parameters": _p({"filename":"string"})},
    {"name": "word_type_text",
     "description": "Active Word document mein text type karo. heading_level: 0=normal, 1-3=heading",
     "parameters": _p({"text":"string","heading_level":"integer","bold":"boolean","italic":"boolean","font_size":"integer","new_line":"boolean"},["text"])},
    {"name": "word_click_button",
     "description": "Word ka ribbon button click karo — bold, italic, underline, align_center, align_left, save, undo, redo, heading1, heading2, bullet_list, numbered_list, find, replace, print, page_break, spell_check",
     "parameters": _p({"button_name":"string"},["button_name"])},
    {"name": "word_insert_table",
     "description": "Word mein table insert karo",
     "parameters": _pa({"rows":"integer","cols":"integer","data":{"type":"array","items":{"type":"array","items":{}}}},["rows","cols"])},
    {"name": "word_format_text",
     "description": "Word mein specific text ko format karo — bold, italic, color, size",
     "parameters": _p({"text_to_find":"string","bold":"boolean","italic":"boolean","color":"string","size":"integer"},["text_to_find"])},
    {"name": "word_get_position",
     "description": "Word mein abhi kahan hain — page number, line, column",
     "parameters": _p({})},

    # ── PowerPoint ─────────────────────────────────────────
    {"name": "ppt_create_presentation",
     "description": "Full PowerPoint presentation banao — 7-8 slides, full content ke saath. Topic batao, baaki TITAN karti hai.",
     "parameters": _pa({
         "topic": "string",
         "slides_content": {"type":"array","items":{"type":"object"}},
         "title": "string",
         "num_slides": "integer"
     },["topic"])},
    {"name": "ppt_add_slide",
     "description": "Existing PPT mein new slide add karo",
     "parameters": _pa({"title":"string","content":"string","bullets":{"type":"array","items":{"type":"string"}},"slide_index":"integer"},["title"])},

    # ── File Management ────────────────────────────────────
    {"name": "file_copy",
     "description": "File ya folder copy karo",
     "parameters": _p({"source":"string","destination":"string","overwrite":"boolean"},["source","destination"])},
    {"name": "file_move",
     "description": "File ya folder move karo",
     "parameters": _p({"source":"string","destination":"string"},["source","destination"])},
    {"name": "file_delete",
     "description": "File ya folder delete karo. to_recycle=True se Recycle Bin mein jaata hai",
     "parameters": _p({"path":"string","to_recycle":"boolean"},["path"])},
    {"name": "file_rename",
     "description": "File ya folder rename karo",
     "parameters": _p({"path":"string","new_name":"string"},["path","new_name"])},
    {"name": "folder_read",
     "description": "Folder ka content padho — files, subfolders, sizes. Khali hone par current active folder dekho.",
     "parameters": _p({"folder_path":"string","show_hidden":"boolean","file_type":"string"})},
    {"name": "file_extract",
     "description": "ZIP/RAR/7z file extract karo",
     "parameters": _p({"archive_path":"string","destination":"string"},["archive_path"])},
    {"name": "file_compress",
     "description": "File ya folder ko ZIP mein compress karo",
     "parameters": _p({"source":"string","output_name":"string","format":"string"},["source"])},
    {"name": "file_merge",
     "description": "Multiple files merge karo — text/pdf/excel",
     "parameters": _pa({"files":{"type":"array","items":{"type":"string"}},"output_path":"string","merge_type":"string"},["files","output_path"])},

    # ── PDF ────────────────────────────────────────────────
    {"name": "pdf_read_file",
     "description": "PDF file padho. file_path khali ho toh currently active/open PDF detect karta hai automatically.",
     "parameters": _p({"file_path":"string","pages":"string"})},
    {"name": "pdf_get_info",
     "description": "PDF ka metadata — pages, size, title, author",
     "parameters": _p({"file_path":"string"})},

    # ── Windows Management ─────────────────────────────────
    {"name": "window_list_all",
     "description": "Sab open windows list karo — title, size, position",
     "parameters": _p({})},
    {"name": "window_focus",
     "description": "Window ko foreground mein lao — title ya HWND se",
     "parameters": _p({"title_or_hwnd":"string"},["title_or_hwnd"])},
    {"name": "window_resize",
     "description": "Window resize aur reposition karo",
     "parameters": _p({"title":"string","width":"integer","height":"integer","x":"integer","y":"integer"},["title","width","height"])},
    {"name": "window_snap_to",
     "description": "Window ko snap karo — left_half, right_half, top_half, bottom_half, top_left, top_right, bottom_left, bottom_right, maximize, minimize",
     "parameters": _p({"title":"string","position":"string"},["title","position"])},
    {"name": "window_close",
     "description": "Window band karo",
     "parameters": _p({"title":"string","force":"boolean"},["title"])},
    {"name": "window_get_active",
     "description": "Abhi jo window active/foreground mein hai uski info",
     "parameters": _p({})},
    {"name": "window_arrange_side_by_side",
     "description": "Do windows ko side-by-side arrange karo",
     "parameters": _p({"title1":"string","title2":"string"},["title1","title2"])},
]

# ══════════════════════════════════════════════════════════════
# DISPATCHER
# ══════════════════════════════════════════════════════════════

OFFICE_TOOL_MAP = {
    # Location
    "get_current_location":       get_current_location,
    "watch_location_realtime":    watch_location_realtime,
    # Excel
    "excel_create_file":          excel_create_file,
    "excel_navigate":             excel_navigate,
    "excel_get_position":         excel_get_position,
    "excel_write_cell":           excel_write_cell,
    "excel_add_headers":          excel_add_headers,
    "excel_add_data_row":         excel_add_data_row,
    "excel_formula":              excel_formula,
    "excel_calculate":            excel_calculate,
    "excel_create_salary_sheet":  excel_create_salary_sheet,
    "excel_read_cell":            excel_read_cell,
    "excel_select_range":         excel_select_range,
    "excel_auto_fit":             excel_auto_fit,
    "excel_add_chart":            excel_add_chart,
    # Word
    "word_create_file":           word_create_file,
    "word_type_text":             word_type_text,
    "word_click_button":          word_click_button,
    "word_insert_table":          word_insert_table,
    "word_format_text":           word_format_text,
    "word_get_position":          word_get_position,
    # PPT
    "ppt_create_presentation":    ppt_create_presentation,
    "ppt_add_slide":              ppt_add_slide,
    # File Management
    "file_copy":                  file_copy,
    "file_move":                  file_move,
    "file_delete":                file_delete,
    "file_rename":                file_rename,
    "folder_read":                folder_read,
    "file_extract":               file_extract,
    "file_compress":              file_compress,
    "file_merge":                 file_merge,
    # PDF
    "pdf_read_file":              pdf_read_file,
    "pdf_get_info":               pdf_get_info,
    # Windows
    "window_list_all":            window_list_all,
    "window_focus":               window_focus,
    "window_resize":              window_resize,
    "window_snap_to":             window_snap_to,
    "window_close":               window_close,
    "window_get_active":          window_get_active,
    "window_arrange_side_by_side":window_arrange_side_by_side,
}

OFFICE_TOOL_NAMES = {t["name"] for t in TITAN_OFFICE_TOOLS}

async def office_dispatch(name: str, args: dict) -> str:
    fn = OFFICE_TOOL_MAP.get(name)
    if fn:
        return await fn(**args)
    return f"❌ Office tool nahi mila: {name}"
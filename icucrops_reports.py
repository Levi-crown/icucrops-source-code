"""Farm report generation for the Reports page.

Two document formats are produced from one shared dataset so the Excel workbook
and the PDF always say the same thing:

* ``build_workbook`` writes a real .xlsx package. Every cell is a live value in
  an unprotected sheet, so the farm can retype a figure or add a column after
  downloading. Numbers are written as numbers, not text, so Excel sums them.
* ``build_pdf`` writes a PDF with an embedded chart and tables laid out to match
  the dashboard's emerald palette.

Both are assembled from the Python standard library alone. Neither openpyxl nor
a PDF toolkit is installed here, and adding one would grow the Vercel function
bundle and the Raspberry Pi install for two documents whose structure is fixed
and known. .xlsx is a ZIP of XML and PDF is a byte-offset container; both are
within reach of ``zipfile`` and ``str``.
"""

from __future__ import annotations

import io
import zlib
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

# The dashboard's emerald tokens, repeated here as the print palette. These are
# the values from assets/icucrops-emerald-theme.css; a report that came back in
# some other green would not read as part of the same product.
GREEN_900 = (0.043, 0.184, 0.129)
GREEN_800 = (0.055, 0.239, 0.169)
GREEN_700 = (0.082, 0.345, 0.235)
GREEN_600 = (0.110, 0.502, 0.314)
GREEN_500 = (0.145, 0.667, 0.404)
GREEN_300 = (0.553, 0.886, 0.678)
INK = (0.063, 0.129, 0.094)
INK_SOFT = (0.322, 0.400, 0.353)
LINE = (0.839, 0.906, 0.851)
SURFACE_SOFT = (0.941, 0.980, 0.929)
PAPER = (1.0, 1.0, 1.0)
AMBER = (0.851, 0.604, 0.086)
BLUE = (0.149, 0.545, 0.910)
RED = (0.847, 0.310, 0.310)

XLSX_HEADER_FILL = "FF0E3D2B"
XLSX_BAND_FILL = "FFF0FAED"
XLSX_TITLE_COLOR = "FF0B2F21"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _xml_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _column_name(index: int) -> str:
    """1 -> A, 27 -> AA."""
    name = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def format_report_period(start: str, end: str) -> str:
    """Render "Aug 1 - 30, 2026" style period text from two ISO dates."""
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
    except (TypeError, ValueError):
        return f"{start} to {end}"

    if start_date.year == end_date.year and start_date.month == end_date.month:
        return f"{start_date.strftime('%b')} {start_date.day} - {end_date.day}, {end_date.year}"
    if start_date.year == end_date.year:
        return (
            f"{start_date.strftime('%b')} {start_date.day} - "
            f"{end_date.strftime('%b')} {end_date.day}, {end_date.year}"
        )
    return (
        f"{start_date.strftime('%b')} {start_date.day}, {start_date.year} - "
        f"{end_date.strftime('%b')} {end_date.day}, {end_date.year}"
    )


def local_timestamp_label(offset_minutes: int = 0) -> str:
    """A human-readable stamp for the footer, shifted to the viewer's clock."""
    try:
        shift = int(offset_minutes)
    except (TypeError, ValueError):
        shift = 0
    shift = max(-14 * 60, min(14 * 60, shift))
    moment = datetime.now(timezone.utc) + timedelta(minutes=shift)
    hour = moment.hour % 12 or 12
    meridiem = "AM" if moment.hour < 12 else "PM"
    return f"{moment.strftime('%b')} {moment.day}, {moment.year}, {hour}:{moment.strftime('%M')} {meridiem}"


# ---------------------------------------------------------------------------
# Excel workbook
# ---------------------------------------------------------------------------


class _SharedStyles:
    """The fixed style table shared by every sheet in the workbook.

    Indices here are referenced by ``s="n"`` on each cell, so the order below is
    the contract: changing it re-styles the whole workbook.
    """

    BODY = 0
    TITLE = 1
    SUBTITLE = 2
    HEADER = 3
    BAND = 4
    NUMBER = 5
    NUMBER_BAND = 6
    SECTION = 7
    TOTAL = 8
    TOTAL_NUMBER = 9


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<numFmts count=\"1\"><numFmt numFmtId=\"164\" formatCode=\"#,##0.00\"/></numFmts>"
        "<fonts count=\"6\">"
        f'<font><sz val="11"/><color rgb="FF102118"/><name val="Calibri"/></font>'
        f'<font><b/><sz val="18"/><color rgb="{XLSX_TITLE_COLOR}"/><name val="Calibri"/></font>'
        '<font><sz val="11"/><color rgb="FF52665A"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        f'<font><b/><sz val="12"/><color rgb="{XLSX_TITLE_COLOR}"/><name val="Calibri"/></font>'
        f'<font><b/><sz val="11"/><color rgb="{XLSX_TITLE_COLOR}"/><name val="Calibri"/></font>'
        "</fonts>"
        "<fills count=\"4\">"
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        f'<fill><patternFill patternType="solid"><fgColor rgb="{XLSX_HEADER_FILL}"/>'
        '<bgColor indexed="64"/></patternFill></fill>'
        f'<fill><patternFill patternType="solid"><fgColor rgb="{XLSX_BAND_FILL}"/>'
        '<bgColor indexed="64"/></patternFill></fill>'
        "</fills>"
        "<borders count=\"2\">"
        "<border><left/><right/><top/><bottom/><diagonal/></border>"
        '<border><left/><right/><top/><bottom style="thin">'
        '<color rgb="FFB9DCC5"/></bottom><diagonal/></border>'
        "</borders>"
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="10">'
        # 0 BODY
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
        '<alignment vertical="center"/></xf>'
        # 1 TITLE
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1">'
        '<alignment vertical="center"/></xf>'
        # 2 SUBTITLE
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1">'
        '<alignment vertical="center"/></xf>'
        # 3 HEADER
        '<xf numFmtId="0" fontId="3" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"'
        ' applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>'
        # 4 BAND
        '<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"'
        ' applyAlignment="1"><alignment vertical="center"/></xf>'
        # 5 NUMBER
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"'
        ' applyAlignment="1"><alignment vertical="center" horizontal="right"/></xf>'
        # 6 NUMBER_BAND
        '<xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFill="1" applyBorder="1"'
        ' applyAlignment="1"><alignment vertical="center" horizontal="right"/></xf>'
        # 7 SECTION
        '<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1">'
        '<alignment vertical="center"/></xf>'
        # 8 TOTAL
        '<xf numFmtId="0" fontId="5" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1"'
        ' applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>'
        # 9 TOTAL_NUMBER
        '<xf numFmtId="0" fontId="5" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1"'
        ' applyBorder="1" applyAlignment="1"><alignment vertical="center" horizontal="right"/></xf>'
        "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _cell_xml(reference: str, value: object, style: int) -> str:
    if value is None or value == "":
        return f'<c r="{reference}" s="{style}"/>'
    if _is_number(value):
        return f'<c r="{reference}" s="{style}"><v>{value}</v></c>'
    return (
        f'<c r="{reference}" s="{style}" t="inlineStr">'
        f"<is><t xml:space=\"preserve\">{_xml_escape(value)}</t></is></c>"
    )


def _sheet_xml(sheet: dict[str, object]) -> str:
    """Render one worksheet.

    A sheet is a list of blocks; each block is a title, an optional header row,
    and data rows. Numbers stay numeric so the workbook stays a spreadsheet
    rather than a picture of one.
    """
    widths: list[float] = list(sheet.get("widths") or [])
    rows_xml: list[str] = []
    row_number = 0

    def emit(cells: list[tuple[object, int]]) -> None:
        nonlocal row_number
        row_number += 1
        rendered = "".join(
            _cell_xml(f"{_column_name(index + 1)}{row_number}", value, style)
            for index, (value, style) in enumerate(cells)
        )
        rows_xml.append(f'<row r="{row_number}">{rendered}</row>')

    for block in sheet.get("blocks") or []:
        kind = block.get("kind", "table")

        if kind == "title":
            emit([(block.get("text", ""), _SharedStyles.TITLE)])
            for line in block.get("lines") or []:
                emit([(line, _SharedStyles.SUBTITLE)])
            emit([])
            continue

        if kind == "table":
            if block.get("title"):
                emit([(block["title"], _SharedStyles.SECTION)])
            headers = list(block.get("headers") or [])
            if headers:
                emit([(header, _SharedStyles.HEADER) for header in headers])
            for index, row in enumerate(block.get("rows") or []):
                banded = index % 2 == 1
                cells: list[tuple[object, int]] = []
                for value in row:
                    if _is_number(value):
                        cells.append(
                            (value, _SharedStyles.NUMBER_BAND if banded else _SharedStyles.NUMBER)
                        )
                    else:
                        cells.append(
                            (value, _SharedStyles.BAND if banded else _SharedStyles.BODY)
                        )
                emit(cells)
            total_row = block.get("total")
            if total_row:
                emit([
                    (
                        value,
                        _SharedStyles.TOTAL_NUMBER if _is_number(value) else _SharedStyles.TOTAL,
                    )
                    for value in total_row
                ])
            emit([])

    columns_xml = ""
    if widths:
        entries = "".join(
            f'<col min="{index + 1}" max="{index + 1}" width="{width}" customWidth="1"/>'
            for index, width in enumerate(widths)
        )
        columns_xml = f"<cols>{entries}</cols>"

    frozen = ""
    freeze_at = int(sheet.get("freezeRow") or 0)
    if freeze_at > 0:
        frozen = (
            f'<sheetViews><sheetView workbookViewId="0">'
            f'<pane ySplit="{freeze_at}" topLeftCell="A{freeze_at + 1}" activePane="bottomLeft"'
            ' state="frozen"/></sheetView></sheetViews>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{frozen}{columns_xml}"
        f'<sheetData>{"".join(rows_xml)}</sheetData>'
        "</worksheet>"
    )


def build_workbook(sheets: list[dict[str, object]]) -> bytes:
    """Package the given sheets as a .xlsx file.

    No sheet protection and no locked cells are written, so every value opens
    editable. That is the point of offering Excel next to PDF.
    """
    usable = [sheet for sheet in sheets if sheet.get("blocks")] or [
        {"name": "Report", "blocks": []}
    ]

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    for index in range(len(usable)):
        content_types.append(
            f'<Override PartName="/xl/worksheets/sheet{index + 1}.xml"'
            ' ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    content_types.append("</Types>")

    sheet_entries = "".join(
        f'<sheet name="{_xml_escape(sheet.get("name") or f"Sheet{index + 1}")}"'
        f' sheetId="{index + 1}" r:id="rId{index + 1}"/>'
        for index, sheet in enumerate(usable)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_entries}</sheets>"
        "</workbook>"
    )

    relationship_entries = "".join(
        f'<Relationship Id="rId{index + 1}"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"'
        f' Target="worksheets/sheet{index + 1}.xml"/>'
        for index in range(len(usable))
    )
    styles_relationship_id = len(usable) + 1
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationship_entries}"
        f'<Relationship Id="rId{styles_relationship_id}"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"'
        ' Target="styles.xml"/>'
        "</Relationships>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "".join(content_types))
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1"'
            ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
            ' Target="xl/workbook.xml"/></Relationships>',
        )
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, sheet in enumerate(usable):
            archive.writestr(f"xl/worksheets/sheet{index + 1}.xml", _sheet_xml(sheet))

    return buffer.getvalue()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

PAGE_WIDTH = 595.28   # A4 portrait, in points
PAGE_HEIGHT = 841.89
MARGIN = 42.0


def _pdf_escape(text: object) -> str:
    return (
        str(text)
        .replace("\\", r"\\")
        .replace("(", r"\(")
        .replace(")", r"\)")
    )


def _pdf_text_width(text: str, size: float, bold: bool = False) -> float:
    """Approximate Helvetica advance width.

    Exact per-glyph metrics are not worth embedding for a fixed report layout;
    this average is close enough to keep text inside its column and to centre a
    heading without it drifting visibly.
    """
    factor = 0.545 if bold else 0.505
    narrow = sum(1 for character in str(text) if character in "iljtIfr .,:;'|!")
    return (len(str(text)) - narrow * 0.42) * size * factor


def _truncate_to_width(text: str, size: float, limit: float, bold: bool = False) -> str:
    value = str(text)
    if _pdf_text_width(value, size, bold) <= limit:
        return value
    while value and _pdf_text_width(value + "...", size, bold) > limit:
        value = value[:-1]
    return f"{value}..." if value else ""


class _Canvas:
    """A single PDF content stream with the drawing primitives this report needs."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.uses_logo = False

    def _color(self, rgb: tuple[float, float, float], stroke: bool = False) -> None:
        operator = "RG" if stroke else "rg"
        self.parts.append(f"{rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f} {operator}")

    def rect(self, x: float, y: float, width: float, height: float, fill: tuple[float, float, float]) -> None:
        self._color(fill)
        self.parts.append(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re f")

    def rounded_rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        radius: float,
        fill: tuple[float, float, float] | None = None,
        stroke: tuple[float, float, float] | None = None,
        line_width: float = 0.8,
    ) -> None:
        radius = max(0.0, min(radius, width / 2, height / 2))
        kappa = radius * 0.5523
        right = x + width
        top = y + height
        self.parts.append(f"{x + radius:.2f} {y:.2f} m")
        self.parts.append(f"{right - radius:.2f} {y:.2f} l")
        self.parts.append(
            f"{right - radius + kappa:.2f} {y:.2f} {right:.2f} {y + radius - kappa:.2f} "
            f"{right:.2f} {y + radius:.2f} c"
        )
        self.parts.append(f"{right:.2f} {top - radius:.2f} l")
        self.parts.append(
            f"{right:.2f} {top - radius + kappa:.2f} {right - radius + kappa:.2f} {top:.2f} "
            f"{right - radius:.2f} {top:.2f} c"
        )
        self.parts.append(f"{x + radius:.2f} {top:.2f} l")
        self.parts.append(
            f"{x + radius - kappa:.2f} {top:.2f} {x:.2f} {top - radius + kappa:.2f} "
            f"{x:.2f} {top - radius:.2f} c"
        )
        self.parts.append(f"{x:.2f} {y + radius:.2f} l")
        self.parts.append(
            f"{x:.2f} {y + radius - kappa:.2f} {x + radius - kappa:.2f} {y:.2f} "
            f"{x + radius:.2f} {y:.2f} c"
        )
        self.parts.append("h")

        if fill is not None and stroke is not None:
            self._color(fill)
            self._color(stroke, stroke=True)
            self.parts.append(f"{line_width:.2f} w B")
        elif fill is not None:
            self._color(fill)
            self.parts.append("f")
        elif stroke is not None:
            self._color(stroke, stroke=True)
            self.parts.append(f"{line_width:.2f} w S")

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: tuple[float, float, float],
        width: float = 0.7,
    ) -> None:
        self._color(color, stroke=True)
        self.parts.append(f"{width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def polyline(
        self,
        points: list[tuple[float, float]],
        color: tuple[float, float, float],
        width: float = 1.4,
    ) -> None:
        if len(points) < 2:
            return
        self._color(color, stroke=True)
        self.parts.append(f"{width:.2f} w 1 J 1 j")
        head, *tail = points
        self.parts.append(f"{head[0]:.2f} {head[1]:.2f} m")
        for point in tail:
            self.parts.append(f"{point[0]:.2f} {point[1]:.2f} l")
        self.parts.append("S")

    def circle(self, x: float, y: float, radius: float, fill: tuple[float, float, float]) -> None:
        kappa = radius * 0.5523
        self._color(fill)
        self.parts.append(f"{x - radius:.2f} {y:.2f} m")
        self.parts.append(
            f"{x - radius:.2f} {y + kappa:.2f} {x - kappa:.2f} {y + radius:.2f} {x:.2f} {y + radius:.2f} c"
        )
        self.parts.append(
            f"{x + kappa:.2f} {y + radius:.2f} {x + radius:.2f} {y + kappa:.2f} {x + radius:.2f} {y:.2f} c"
        )
        self.parts.append(
            f"{x + radius:.2f} {y - kappa:.2f} {x + kappa:.2f} {y - radius:.2f} {x:.2f} {y - radius:.2f} c"
        )
        self.parts.append(
            f"{x - kappa:.2f} {y - radius:.2f} {x - radius:.2f} {y - kappa:.2f} {x - radius:.2f} {y:.2f} c"
        )
        self.parts.append("f")

    def logo(self, x: float, y: float, width: float, height: float) -> None:
        """Place the embedded, official ICuCrops logo image."""
        self.uses_logo = True
        self.parts.append(
            f"q {width:.2f} 0 0 {height:.2f} {x:.2f} {y:.2f} cm /Logo Do Q"
        )

    def text(
        self,
        x: float,
        y: float,
        value: object,
        size: float = 10.0,
        color: tuple[float, float, float] = INK,
        bold: bool = False,
    ) -> None:
        font = "F2" if bold else "F1"
        self._color(color)
        self.parts.append(
            f"BT /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td ({_pdf_escape(value)}) Tj ET"
        )

    def text_right(
        self,
        right_x: float,
        y: float,
        value: object,
        size: float = 10.0,
        color: tuple[float, float, float] = INK,
        bold: bool = False,
    ) -> None:
        self.text(right_x - _pdf_text_width(value, size, bold), y, value, size, color, bold)

    def text_center(
        self,
        center_x: float,
        y: float,
        value: object,
        size: float = 10.0,
        color: tuple[float, float, float] = INK,
        bold: bool = False,
    ) -> None:
        self.text(center_x - _pdf_text_width(value, size, bold) / 2, y, value, size, color, bold)

    def render(self) -> bytes:
        return "\n".join(self.parts).encode("latin-1", errors="replace")


def _load_logo_xobject() -> tuple[int, int, bytes]:
    logo_path = Path(__file__).resolve().parent / "assets" / "icucrops-logo-mark.png"
    with Image.open(logo_path) as source:
        image = source.convert("RGBA")
        image.thumbnail((160, 160), Image.Resampling.LANCZOS)
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image.convert("RGB"), mask=image.getchannel("A"))
        width, height = background.size
        return width, height, zlib.compress(background.tobytes(), 9)


def build_pdf(pages: list[_Canvas]) -> bytes:
    """Assemble finished canvases into a PDF file with a valid xref table."""
    if not pages:
        pages = [_Canvas()]

    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_regular = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    font_bold = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )

    logo_id: int | None = None
    if any(page.uses_logo for page in pages):
        logo_width, logo_height, logo_data = _load_logo_xobject()
        logo_id = add(
            (
                f"<< /Type /XObject /Subtype /Image /Width {logo_width} "
                f"/Height {logo_height} /ColorSpace /DeviceRGB /BitsPerComponent 8 "
                f"/Filter /FlateDecode /Interpolate true /Length {len(logo_data)} >>\nstream\n"
            ).encode("ascii")
            + logo_data
            + b"\nendstream"
        )

    # The pages object needs its children's numbers, and each child needs the
    # parent's, so the id is reserved before either exists.
    pages_object_id = len(objects) + 1
    objects.append(b"")

    page_ids: list[int] = []
    for page in pages:
        # Text-heavy activity tables compress especially well. Keeping page
        # streams deflated makes long monthly reports substantially smaller to
        # transfer while adding only a few milliseconds during generation.
        stream = zlib.compress(page.render(), 6)
        content_id = add(
            b"<< /Filter /FlateDecode /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
        xobject_resources = (
            f"/XObject << /Logo {logo_id} 0 R >> " if logo_id and page.uses_logo else ""
        )
        page_ids.append(
            add(
                (
                    f"<< /Type /Page /Parent {pages_object_id} 0 R "
                    f"/MediaBox [0 0 {PAGE_WIDTH:.2f} {PAGE_HEIGHT:.2f}] "
                    f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R >> "
                    f"{xobject_resources}>> "
                    f"/Contents {content_id} 0 R >>"
                ).encode("latin-1")
            )
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_object_id - 1] = (
        f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>"
    ).encode("latin-1")

    catalog_id = add(f"<< /Type /Catalog /Pages {pages_object_id} 0 R >>".encode("latin-1"))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_position = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF\n"
    ).encode("ascii")

    return bytes(out)


# ---------------------------------------------------------------------------
# Report page composition
# ---------------------------------------------------------------------------


def _draw_page_frame(canvas: _Canvas, page_number: int, page_count: int, footer_note: str = "") -> None:
    # The page background is painted by the caller before any content. Filling
    # it again here would run last in the content stream and cover the report.
    footer_y = MARGIN - 14
    canvas.line(MARGIN, MARGIN - 2, PAGE_WIDTH - MARGIN, MARGIN - 2, LINE)
    canvas.text(MARGIN, footer_y, "ICuCrops", 8.5, GREEN_700, bold=True)
    if footer_note:
        canvas.text_center(PAGE_WIDTH / 2, footer_y, footer_note, 7.5, INK_SOFT)
    canvas.text_right(
        PAGE_WIDTH - MARGIN, footer_y, f"Page {page_number} of {page_count}", 8.5, INK_SOFT
    )


def _draw_card(
    canvas: _Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    fill: tuple[float, float, float] = PAPER,
) -> None:
    canvas.rounded_rect(x, y, width, height, 8, fill=fill, stroke=LINE, line_width=0.8)


def _draw_metric_tiles(canvas: _Canvas, top_y: float, metrics: list[dict[str, object]]) -> float:
    """A row of summary tiles. Returns the y coordinate below the row."""
    if not metrics:
        return top_y

    available = PAGE_WIDTH - MARGIN * 2
    gap = 8.0
    count = len(metrics)
    tile_width = (available - gap * (count - 1)) / count
    tile_height = 58.0
    tile_y = top_y - tile_height

    for index, metric in enumerate(metrics):
        x = MARGIN + index * (tile_width + gap)
        _draw_card(canvas, x, tile_y, tile_width, tile_height, SURFACE_SOFT)
        label = _truncate_to_width(str(metric.get("label", "")), 7.5, tile_width - 16)
        canvas.text_center(x + tile_width / 2, tile_y + tile_height - 18, label, 7.5, INK_SOFT)
        value = _truncate_to_width(str(metric.get("value", "")), 16, tile_width - 12, bold=True)
        canvas.text_center(x + tile_width / 2, tile_y + 20, value, 16, GREEN_700, bold=True)
        unit = str(metric.get("unit", "") or "")
        sample_count = int(metric.get("sampleCount") or 0)
        detail = unit
        if sample_count:
            detail = f"{unit + ' - ' if unit else ''}{sample_count:,} sampled points"
        if detail:
            detail = _truncate_to_width(detail, 6.2, tile_width - 8)
            canvas.text_center(x + tile_width / 2, tile_y + 9, detail, 6.2, INK_SOFT)

    return tile_y


TABLE_HEADER_HEIGHT = 20.0
TABLE_ROW_HEIGHT = 17.0
# Nothing may be drawn below this line; the footer rule and page number live there.
CONTENT_FLOOR = MARGIN + 16


def table_rows_that_fit(top_y: float, *, reserve: float = 0.0) -> int:
    """How many body rows fit between ``top_y`` and the bottom margin."""
    available = top_y - TABLE_HEADER_HEIGHT - CONTENT_FLOOR - reserve
    return max(0, int(available // TABLE_ROW_HEIGHT))


def _draw_table(
    canvas: _Canvas,
    top_y: float,
    headers: list[str],
    rows: list[list[object]],
    widths: list[float],
    total_row: list[object] | None = None,
    empty_message: str = "No records in this period.",
    max_rows: int | None = None,
) -> float:
    """Draw a table and return the y coordinate below it.

    ``max_rows`` caps what is drawn so a long table stops at the bottom margin
    instead of running off the page. The caller decides what to do with the
    rows that did not fit; ``table_rows_that_fit`` computes the cap.
    """
    if max_rows is not None and max_rows >= 0:
        rows = rows[:max_rows]
    x_start = MARGIN
    table_width = PAGE_WIDTH - MARGIN * 2
    scale = table_width / sum(widths) if widths and sum(widths) else 1.0
    columns = [width * scale for width in widths]
    header_height = 20.0
    row_height = 17.0

    # Which columns are numeric, decided once from the body and applied to the
    # header, every cell and the total alike.
    #
    # It used to be decided per cell: a numeric value was pushed right while
    # its own header stayed left, so "Days Grown" sat over the left edge of a
    # column whose 15, 37, 36 sat against the right one. The total row had the
    # opposite half of the same bug -- it right-aligned every column after the
    # first, so "1 harvested" floated right of the "Outcome" words it was
    # summing. Both read as a table whose columns do not line up, because they
    # did not. A column is text or numbers, and the whole column follows that.
    #
    # Numbers are then centred in their column rather than pushed to its right
    # edge. Right-aligning is the ledger convention and it is the correct one
    # when a rule or a gridline closes the column, which is how the .xlsx
    # reads. This page has neither: the columns are laid out on bare paper, so
    # a right-aligned number ends 6pt from the left edge of the next column's
    # text and the eye reads the two as one run -- "15 -", "2 Fertilizer",
    # "107 Sep 22, 2026". Centring leaves clear space on both sides, so each
    # column is its own lane and the digits still share one axis down the page.
    numeric_columns: set[int] = set()
    for column_index in range(len(headers)):
        if column_index == 0:
            # The first column is the row's label, never a measurement, even
            # when it happens to read as a number.
            continue
        values = [
            row[column_index]
            for row in rows
            if column_index < len(row) and str(row[column_index]).strip() not in ("", "-")
        ]
        if values and all(_is_number(value) for value in values):
            numeric_columns.add(column_index)

    canvas.rect(x_start, top_y - header_height, table_width, header_height, GREEN_800)
    text_y = top_y - header_height + 6.5
    x = x_start
    for index, header in enumerate(headers):
        column_width = columns[index] if index < len(columns) else 0
        label = _truncate_to_width(header, 7.8, column_width - 12, bold=True)
        if index in numeric_columns:
            canvas.text_center(x + column_width / 2, text_y, label, 7.8, PAPER, bold=True)
        else:
            canvas.text(x + 6, text_y, label, 7.8, PAPER, bold=True)
        x += column_width

    y = top_y - header_height

    if not rows:
        canvas.rect(x_start, y - row_height, table_width, row_height, PAPER)
        canvas.text(x_start + 6, y - row_height + 5.5, empty_message, 8, INK_SOFT)
        y -= row_height
        canvas.line(x_start, y, x_start + table_width, y, LINE)
        return y

    for row_index, row in enumerate(rows):
        y -= row_height
        if row_index % 2 == 1:
            canvas.rect(x_start, y, table_width, row_height, SURFACE_SOFT)
        x = x_start
        for column_index, value in enumerate(row):
            column_width = columns[column_index] if column_index < len(columns) else 0
            cell = _truncate_to_width(str(value), 8, column_width - 12)
            if column_index in numeric_columns:
                canvas.text_center(x + column_width / 2, y + 5.5, cell, 8, INK)
            else:
                canvas.text(x + 6, y + 5.5, cell, 8, INK)
            x += column_width
        canvas.line(x_start, y, x_start + table_width, y, LINE, 0.5)

    if total_row:
        y -= row_height
        canvas.rect(x_start, y, table_width, row_height, SURFACE_SOFT)
        x = x_start
        for column_index, value in enumerate(total_row):
            column_width = columns[column_index] if column_index < len(columns) else 0
            if value in (None, ""):
                x += column_width
                continue
            # A label may run into the empty cells beside it rather than being
            # cut. "Total (Period)" needs 52pt and the Row column is 36pt wide,
            # so it used to print as "Total (..." -- a summary line that does
            # not say what it is summing. Nothing is overwritten: the run stops
            # at the first cell that has its own content.
            available = column_width
            if not numeric_columns or column_index not in numeric_columns:
                for next_index in range(column_index + 1, len(total_row)):
                    if str(total_row[next_index] or "").strip():
                        break
                    available += columns[next_index] if next_index < len(columns) else 0
            cell = _truncate_to_width(str(value), 8, available - 12, bold=True)
            if column_index in numeric_columns:
                canvas.text_center(x + column_width / 2, y + 5.5, cell, 8, GREEN_800, bold=True)
            else:
                canvas.text(x + 6, y + 5.5, cell, 8, GREEN_800, bold=True)
            x += column_width
        canvas.line(x_start, y, x_start + table_width, y, LINE)

    return y


def _parse_chart_moment(value: object) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _chart_number(value: float) -> str:
    absolute = abs(value)
    if absolute >= 100:
        return f"{value:.0f}"
    if absolute >= 10:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _draw_sensor_trend_charts(
    canvas: _Canvas,
    top_y: float,
    height: float,
    series: list[dict[str, object]],
    start_value: object,
    end_value: object,
) -> float:
    """Small multiples with raw readings on real time and value axes."""
    columns = 2
    rows = 2
    gap = 8.0
    available_width = PAGE_WIDTH - MARGIN * 2
    card_width = (available_width - gap) / columns
    card_height = (height - gap) / rows
    start = _parse_chart_moment(start_value)
    end = _parse_chart_moment(end_value)
    if not start or not end or end <= start:
        end = start + timedelta(days=1) if start else datetime.now(timezone.utc)
        start = start or end - timedelta(days=1)
    time_span = max((end - start).total_seconds(), 1.0)

    entries = list(series[:4])
    while len(entries) < columns * rows:
        entries.append({"label": "Sensor", "unit": "", "points": []})

    for index, entry in enumerate(entries):
        column = index % columns
        row = index // columns
        x = MARGIN + column * (card_width + gap)
        card_top = top_y - row * (card_height + gap)
        card_bottom = card_top - card_height
        _draw_card(canvas, x, card_bottom, card_width, card_height, PAPER)

        color = entry.get("color", GREEN_500)
        label = str(entry.get("label") or "Sensor")
        unit = str(entry.get("unit") or "")
        canvas.line(x + 9, card_top - 12, x + 20, card_top - 12, color, 1.8)
        canvas.text(x + 24, card_top - 15, label, 7.8, INK, bold=True)

        parsed: list[tuple[datetime, float]] = []
        for point in entry.get("points") or []:
            if not isinstance(point, dict):
                continue
            moment = _parse_chart_moment(point.get("capturedAt"))
            try:
                value = float(point.get("value"))
            except (TypeError, ValueError):
                continue
            if moment and start <= moment <= end:
                parsed.append((moment, value))
        parsed.sort(key=lambda item: item[0])

        plot_left = x + 34
        plot_right = x + card_width - 9
        plot_bottom = card_bottom + 15
        plot_top = card_top - 24
        plot_width = plot_right - plot_left
        plot_height = plot_top - plot_bottom

        if not parsed:
            canvas.text_center(
                (plot_left + plot_right) / 2,
                plot_bottom + plot_height / 2 - 2,
                "No readings in this period",
                7.2,
                INK_SOFT,
            )
            continue

        values = [value for _, value in parsed]
        minimum = min(values)
        maximum = max(values)
        padding = max((maximum - minimum) * 0.08, abs(maximum) * 0.02, 0.1)
        lower = minimum - padding
        upper = maximum + padding
        if minimum >= 0:
            lower = max(0.0, lower)
        value_span = max(upper - lower, 0.1)

        canvas.line(plot_left, plot_bottom, plot_right, plot_bottom, LINE, 0.5)
        canvas.line(plot_left, plot_top, plot_right, plot_top, LINE, 0.5)
        unit_suffix = f" {unit}" if unit else ""
        canvas.text_right(
            plot_left - 4, plot_top - 2.5, f"{_chart_number(upper)}", 5.8, INK_SOFT
        )
        canvas.text_right(
            plot_left - 4, plot_bottom - 2.5, f"{_chart_number(lower)}", 5.8, INK_SOFT
        )

        coordinates = [
            (
                plot_left + plot_width * ((moment - start).total_seconds() / time_span),
                plot_bottom + plot_height * ((value - lower) / value_span),
            )
            for moment, value in parsed
        ]
        canvas.polyline(coordinates, color, 1.2)
        for point_x, point_y in coordinates:
            canvas.circle(point_x, point_y, 1.15, color)

        latest = values[-1]
        canvas.text_right(
            plot_right,
            card_top - 15,
            f"Latest {_chart_number(latest)}{unit_suffix}",
            6.4,
            color,
            bold=True,
        )
        canvas.text(plot_left, card_bottom + 5, f"{start.strftime('%b')} {start.day}", 5.7, INK_SOFT)
        canvas.text_right(
            plot_right, card_bottom + 5, f"{end.strftime('%b')} {end.day}", 5.7, INK_SOFT
        )

    return top_y - height


def compose_report_pages(report: dict[str, object]) -> list[_Canvas]:
    """Lay out the farm report as PDF pages.

    Page 1 carries the identity, the period averages, the sensor trend and the
    per-row health. Page 2 carries the activity tables. Sections the caller did
    not ask for are skipped and the page count follows, so a narrow export is
    one page rather than one page plus a mostly empty second.
    """
    sections = set(report.get("sections") or [])
    farm_name = str(report.get("farmName") or "ICuCrops Farm")
    period = str(report.get("period") or "")
    generated = str(report.get("generatedAt") or "")
    footer_note = f"Generated by ICuCrops, {generated}" if generated else ""

    first = _Canvas()
    first.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, PAPER)
    y = PAGE_HEIGHT - MARGIN

    first.logo(MARGIN, y - 27, 27, 27)
    first.text(MARGIN + 34, y - 18, "ICuCrops", 15, GREEN_700, bold=True)
    y -= 34

    first.text(MARGIN, y - 16, "Farm Monitoring Report", 21, INK, bold=True)
    y -= 24
    if period:
        first.text(MARGIN, y - 14, f"Reporting Period: {period}", 9.5, INK_SOFT)
        y -= 18
    first.line(MARGIN, y - 8, MARGIN + 190, y - 8, GREEN_500, 2.2)
    y -= 22

    first.text(MARGIN, y - 8, "FARM", 7, INK_SOFT, bold=True)
    y -= 10
    first.text(MARGIN, y - 12, farm_name.upper(), 13, GREEN_800, bold=True)
    y -= 24

    metrics = list(report.get("metrics") or [])
    if metrics:
        y = _draw_metric_tiles(first, y, metrics) - 20

    if "sensors" in sections:
        first.text(MARGIN, y - 10, "Recorded Sensor Trends", 11.5, INK, bold=True)
        y -= 20
        y = _draw_sensor_trend_charts(
            first,
            y,
            168,
            list(report.get("series") or []),
            report.get("chartStart"),
            report.get("chartEnd"),
        ) - 14

    rows = list(report.get("rowHealth") or [])
    if "cultivations" in sections and rows:
        first.text(MARGIN, y - 10, "Row Health Overview", 11.5, INK, bold=True)
        y -= 22
        available = PAGE_WIDTH - MARGIN * 2
        gap = 8.0
        card_width = (available - gap * (len(rows) - 1)) / len(rows)
        card_height = 92.0
        card_y = y - card_height
        for index, row in enumerate(rows):
            x = MARGIN + index * (card_width + gap)
            _draw_card(first, x, card_y, card_width, card_height)
            first.text(
                x + 10,
                card_y + card_height - 17,
                _truncate_to_width(str(row.get("label", "")), 9.5, card_width - 20, bold=True),
                9.5,
                INK,
                bold=True,
            )
            first.text(
                x + 10,
                card_y + card_height - 29,
                _truncate_to_width(str(row.get("crop", "")), 7.8, card_width - 20),
                7.8,
                INK_SOFT,
            )
            first.line(
                x + 10,
                card_y + card_height - 36,
                x + card_width - 10,
                card_y + card_height - 36,
                LINE,
                0.6,
            )

            grade = str(row.get("grade", ""))
            grade_color = row.get("gradeColor", GREEN_600)
            first.circle(x + 26, card_y + 34, 15, SURFACE_SOFT)
            first.text_center(x + 26, card_y + 31, grade, 7.4, grade_color, bold=True)

            first.text(x + 48, card_y + 45, "Sampled Score", 6.8, INK_SOFT)
            score = row.get("score")
            first.text(
                x + 48,
                card_y + 31,
                f"{score}%" if score is not None else "n/a",
                13,
                INK,
                bold=True,
            )
            first.text(x + 48, card_y + 19, "Status", 6.8, INK_SOFT)
            first.text(
                x + 48,
                card_y + 8,
                _truncate_to_width(
                    f"{row.get('trend', '')} - {int(row.get('samples') or 0)} pts",
                    7.6,
                    card_width - 58,
                ),
                7.6,
                grade_color,
                bold=True,
            )
        y = card_y - 16

    # "cultivations" is here as well as on the first page. The first page draws
    # its Row Health cards; the finished-cultivation summary and history table
    # belong with the other tables on the pages that follow, and without this
    # the page they draw on was never opened and the section silently vanished.
    second_sections = [
        section
        for section in ("cultivations", "irrigation", "alerts", "health")
        if section in sections
    ]
    pages = [first]

    if second_sections:
        # A farm with a busy month has more irrigation runs than one page can
        # hold, and the sections after the table still have to appear. Pages are
        # opened on demand instead of being fixed at two.
        def start_page() -> tuple[_Canvas, float]:
            canvas = _Canvas()
            canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, PAPER)
            cursor = PAGE_HEIGHT - MARGIN
            canvas.logo(MARGIN, cursor - 22, 22, 22)
            canvas.text(MARGIN + 28, cursor - 15, "ICuCrops", 11.5, GREEN_700, bold=True)
            canvas.text_right(PAGE_WIDTH - MARGIN, cursor - 10, farm_name, 9, INK_SOFT)
            pages.append(canvas)
            return canvas, cursor - 30

        second, y2 = start_page()

        def ensure_space(canvas: _Canvas, cursor: float, needed: float) -> tuple[_Canvas, float]:
            """Move to a new page when the next block cannot fit below."""
            if cursor - needed >= CONTENT_FLOOR:
                return canvas, cursor
            return start_page()

        if "cultivations" in sections:
            history = report.get("cultivationHistory") or {}
            history_rows = list(history.get("pdfRows") or history.get("rows") or [])
            harvested = int(history.get("harvested") or 0)
            removed = int(history.get("removed") or 0)
            on_schedule = int(history.get("onSchedule") or 0)
            finished = int(history.get("finished") or 0)

            # The chart first, because it is the answer to "how did the season
            # go" and the table below it is the working. Three bars rather than
            # a line: what finished is a count of discrete events, and drawing
            # counts as a trend over time would invent a shape the data does
            # not have.
            chart_height = 96.0
            second, y2 = ensure_space(second, y2, 22 + chart_height + 16)
            second.text(MARGIN, y2 - 10, "Cultivation Summary", 11.5, INK, bold=True)
            y2 -= 22

            bars = [
                ("Harvested", harvested, GREEN_600),
                ("Removed", removed, AMBER),
                ("On Schedule", on_schedule, GREEN_700),
            ]
            chart_y = y2 - chart_height
            _draw_card(second, MARGIN, chart_y, PAGE_WIDTH - MARGIN * 2, chart_height)

            if finished:
                # Scaled to the largest bar rather than to the total, so a
                # season of two removals against twenty harvests still shows a
                # readable removals bar instead of a line at the axis.
                peak = max(1, max(value for _label, value, _color in bars))
                plot_left = MARGIN + 18
                plot_right = PAGE_WIDTH - MARGIN - 18
                plot_bottom = chart_y + 26
                plot_top = chart_y + chart_height - 20
                span = plot_top - plot_bottom
                slot = (plot_right - plot_left) / len(bars)
                bar_width = min(58.0, slot * 0.46)
                for index, (label, value, color) in enumerate(bars):
                    centre = plot_left + slot * (index + 0.5)
                    height = span * (value / peak) if peak else 0.0
                    # A zero still gets a sliver, so the label beneath it reads
                    # as "none of these" rather than as a missing bar.
                    height = max(height, 1.5)
                    second.rect(centre - bar_width / 2, plot_bottom, bar_width, height, color)
                    second.text_center(centre, plot_bottom + height + 5, str(value), 9.0, INK, bold=True)
                    second.text_center(centre, chart_y + 13, label, 7.6, INK_SOFT)
                second.line(plot_left, plot_bottom, plot_right, plot_bottom, LINE, 0.6)
            else:
                second.text_center(
                    PAGE_WIDTH / 2,
                    chart_y + chart_height / 2 - 4,
                    "No cultivations finished in this period.",
                    8.5,
                    INK_SOFT,
                )
            y2 = chart_y - 16

            # Then the table, paginating the way every other table here does.
            headers = list(history.get("headers") or [])
            widths = list(history.get("widths") or [])
            pending = list(history_rows)
            omitted = int(history.get("omittedFromPdf") or 0)
            total_row = list(history.get("total") or []) or None
            heading = "Cultivation History"
            shown = len(pending)

            while True:
                second, y2 = ensure_space(
                    second, y2, 22 + TABLE_HEADER_HEIGHT + TABLE_ROW_HEIGHT * 2
                )
                second.text(MARGIN, y2 - 10, heading, 11.5, INK, bold=True)
                y2 -= 22
                capacity = table_rows_that_fit(y2, reserve=TABLE_ROW_HEIGHT if total_row else 0)
                slice_rows = pending[:capacity] if capacity else []
                is_last = len(slice_rows) >= len(pending)
                y2 = _draw_table(
                    second,
                    y2,
                    headers,
                    slice_rows,
                    widths,
                    total_row if is_last else None,
                    "No cultivations finished in this period.",
                ) - 22
                pending = pending[len(slice_rows):]
                if not pending:
                    if omitted:
                        second.text(
                            MARGIN,
                            y2 + 8,
                            f"Showing the {shown} most recent; "
                            f"{omitted} earlier cultivation(s) are outside this summary.",
                            7.4,
                            INK_SOFT,
                        )
                    break
                heading = "Cultivation History (continued)"
                second, y2 = start_page()

        if "irrigation" in sections:
            irrigation = report.get("irrigation") or {}
            headers = list(irrigation.get("headers") or [])
            widths = list(irrigation.get("widths") or [])
            # The printed report shows the most recent runs; the workbook holds
            # the full history. A caller that supplies no slice gets every row.
            pending = list(irrigation.get("pdfRows") or irrigation.get("rows") or [])
            omitted = int(irrigation.get("omittedFromPdf") or 0)
            total_row = list(irrigation.get("total") or []) or None
            heading = "Irrigation Activity"

            while True:
                second, y2 = ensure_space(
                    second, y2, 22 + TABLE_HEADER_HEIGHT + TABLE_ROW_HEIGHT * 2
                )
                second.text(MARGIN, y2 - 10, heading, 11.5, INK, bold=True)
                y2 -= 22
                # The total belongs with the final slice, so reserve its row only
                # when this slice is the one that will carry it.
                capacity = table_rows_that_fit(y2, reserve=TABLE_ROW_HEIGHT if total_row else 0)
                slice_rows = pending[:capacity] if capacity else []
                is_last = len(slice_rows) >= len(pending)
                y2 = _draw_table(
                    second,
                    y2,
                    headers,
                    slice_rows,
                    widths,
                    total_row if is_last else None,
                    "No irrigation runs recorded in this period.",
                ) - 22
                pending = pending[len(slice_rows):]
                if not pending:
                    if omitted:
                        second.text(
                            MARGIN,
                            y2 + 8,
                            f"Showing the {len(irrigation.get('pdfRows') or [])} most recent runs; "
                            f"{omitted} earlier run(s) are outside this summary.",
                            7.4,
                            INK_SOFT,
                        )
                    break
                heading = "Irrigation Activity (continued)"
                second, y2 = start_page()

        # Alerts is a table now, so it reserves what a table needs to start --
        # its heading, a header row and a couple of body rows -- and paginates
        # itself from there, exactly as Irrigation Activity does. Sensor Health
        # is still a fixed strip of tiles.
        alerts_needed = 22 + TABLE_HEADER_HEIGHT + TABLE_ROW_HEIGHT * 2
        if "health" in sections:
            second, y2 = ensure_space(second, y2, 82)

        if "alerts" in sections:
            alerts = report.get("alerts") or {}
            # Older callers handed a list of cards. Nothing in the app does
            # any more, but a hand-built model in a test might, and a report
            # is not worth crashing over a shape.
            if isinstance(alerts, list):
                alerts = {"headers": [], "widths": [], "rows": [], "pdfRows": []}
            headers = list(alerts.get("headers") or [])
            widths = list(alerts.get("widths") or [])
            pending = list(alerts.get("pdfRows") or alerts.get("rows") or [])
            omitted = int(alerts.get("omittedFromPdf") or 0)
            total_row = list(alerts.get("total") or []) or None
            heading = "Alerts"
            shown = len(pending)

            while True:
                second, y2 = ensure_space(second, y2, alerts_needed)
                second.text(MARGIN, y2 - 10, heading, 11.5, INK, bold=True)
                y2 -= 22
                capacity = table_rows_that_fit(y2, reserve=TABLE_ROW_HEIGHT if total_row else 0)
                slice_rows = pending[:capacity] if capacity else []
                is_last = len(slice_rows) >= len(pending)
                y2 = _draw_table(
                    second,
                    y2,
                    headers,
                    slice_rows,
                    widths,
                    total_row if is_last else None,
                    "No alerts were raised in this period.",
                ) - 22
                pending = pending[len(slice_rows):]
                if not pending:
                    if omitted:
                        second.text(
                            MARGIN,
                            y2 + 8,
                            f"Showing the {shown} most frequent alerts; "
                            f"{omitted} further alert(s) are outside this summary.",
                            7.4,
                            INK_SOFT,
                        )
                    break
                heading = "Alerts (continued)"
                second, y2 = start_page()

        if "health" in sections:
            second, y2 = ensure_space(second, y2, 82)
            second.text(MARGIN, y2 - 10, "Sensor Health", 11.5, INK, bold=True)
            y2 -= 20
            tiles = list(report.get("sensorHealth") or [])
            if tiles:
                gap = 8.0
                tile_width = (PAGE_WIDTH - MARGIN * 2 - gap * (len(tiles) - 1)) / len(tiles)
                tile_height = 46.0
                tile_y = y2 - tile_height
                for index, tile in enumerate(tiles):
                    x = MARGIN + index * (tile_width + gap)
                    _draw_card(second, x, tile_y, tile_width, tile_height, SURFACE_SOFT)
                    second.text_center(
                        x + tile_width / 2,
                        tile_y + tile_height - 16,
                        _truncate_to_width(str(tile.get("label", "")), 7.4, tile_width - 12),
                        7.4,
                        INK_SOFT,
                    )
                    second.text_center(
                        x + tile_width / 2,
                        tile_y + 12,
                        str(tile.get("value", "")),
                        15,
                        tile.get("color", GREEN_700),
                        bold=True,
                    )
                y2 = tile_y - 16

    for index, page in enumerate(pages, start=1):
        _draw_page_frame(page, index, len(pages), footer_note if index == len(pages) else "")

    return pages


def build_report_pdf(report: dict[str, object]) -> bytes:
    return build_pdf(compose_report_pages(report))

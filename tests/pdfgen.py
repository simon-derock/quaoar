# builds tiny text pdfs for tests, so no third-party document is ever committed
def make_pdf(pages: list[list[str]]) -> bytes:
    page_numbers = [4 + 2 * i for i in range(len(pages))]
    kids = " ".join(f"{n} 0 R" for n in page_numbers)
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for number, lines in zip(page_numbers, pages, strict=True):
        stream = content_stream(lines)
        objects[number] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {number + 1} 0 R >>"
        ).encode()
        objects[number + 1] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
    return serialize(objects)


def content_stream(lines: list[str]) -> bytes:
    ops = ["BT", "/F1 11 Tf", "14 TL", "72 760 Td"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"({safe}) Tj T*")
    ops.append("ET")
    return "\n".join(ops).encode("latin-1")


def serialize(objects: dict[int, bytes]) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"
    xref = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode() + b"0000000000 65535 f \n"
    for number in range(1, size):
        out += f"{offsets[number]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)

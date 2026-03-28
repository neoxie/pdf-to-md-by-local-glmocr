#!/usr/bin/env python3
"""PDF to Markdown converter using GLM-OCR."""

import argparse
import base64
import io
import shutil
import sys
from pathlib import Path

import requests
from glmocr import GlmOcr
from pdf2image import convert_from_path
from PIL import Image

MAX_DIM = 1024  # Max pixel dimension for images sent to model
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "glm-ocr:latest"


def check_poppler() -> None:
    """Check if poppler is installed (required by pdf2image)."""
    if not shutil.which("pdftoppm"):
        print("Error: poppler not found.", file=sys.stderr)
        print("Install with:", file=sys.stderr)
        print("  macOS:   brew install poppler", file=sys.stderr)
        print("  Ubuntu:  sudo apt-get install poppler-utils", file=sys.stderr)
        print("  Windows: conda install -c conda-forge poppler", file=sys.stderr)
        print("           或下载 https://github.com/oschwartz10612/poppler-windows/releases", file=sys.stderr)
        sys.exit(1)


def check_ollama_service() -> None:
    """Check if Ollama service is running and GLM-OCR model is available."""
    import json
    import urllib.request

    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            models = json.loads(resp.read()).get("models", [])
            if not any("glm-ocr" in m.get("name", "") for m in models):
                print("Error: GLM-OCR model not found.", file=sys.stderr)
                print("Please run: ollama pull glm-ocr", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        print(f"Error: Cannot connect to Ollama service: {e}", file=sys.stderr)
        print("Please ensure Ollama is running: ollama serve", file=sys.stderr)
        sys.exit(1)


def resize_image(image: Image.Image, max_dim: int = MAX_DIM) -> Image.Image:
    """Resize image to fit within max_dim while preserving aspect ratio."""
    width, height = image.size
    if max(width, height) <= max_dim:
        return image

    if width > height:
        new_width = max_dim
        new_height = int(height * max_dim / width)
    else:
        new_height = max_dim
        new_width = int(width * max_dim / height)

    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def pdf_to_images(pdf_path: Path, dpi: int = 150) -> list[Image.Image]:
    """Convert PDF to list of PIL images."""
    print(f"Converting PDF to images: {pdf_path}")
    images = convert_from_path(pdf_path, dpi=dpi)
    print(f"Converted {len(images)} pages")
    return images


def ocr_via_ollama_api(image: Image.Image, prompt: str = "Recognize the text in the image and output in Markdown format. Preserve the original layout (headings/paragraphs/tables/formulas). Do not fabricate content that does not exist in the image.") -> str:
    """Direct Ollama API call as fallback when glmocr pipeline fails."""
    # Convert image to base64
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }

    response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(f"Ollama API error: {response.status_code} - {response.text[:200]}")

    result = response.json()
    return result.get("response", "").strip()


def image_to_markdown(ocr: GlmOcr, image: Image.Image, use_fallback: bool = True) -> str:
    """Use GLM-OCR to convert image to markdown.

    Falls back to direct Ollama API if glmocr pipeline fails.
    """
    import tempfile

    # Resize image for better performance
    image = resize_image(image)

    # Save to temp file for glmocr
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        image.save(tmp.name, format="PNG")
        tmp_path = tmp.name

    try:
        result = ocr.parse(tmp_path)
        if result.markdown_result is None:
            raise ValueError("OCR returned empty result")
        return result.markdown_result
    except Exception as e:
        if not use_fallback:
            raise
        # Fallback to direct Ollama API
        print(f"  glmocr failed ({e}), falling back to direct Ollama API...")
        return ocr_via_ollama_api(image)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def convert_pdf_to_markdown(pdf_path: Path, output_path: Path) -> None:
    """Convert PDF file to Markdown file."""
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Check dependencies
    check_poppler()
    check_ollama_service()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert PDF to images
    try:
        images = pdf_to_images(pdf_path)
    except Exception as e:
        print(f"Error converting PDF to images: {e}", file=sys.stderr)
        print("Hint: Ensure poppler is installed (macOS: brew install poppler)", file=sys.stderr)
        sys.exit(1)

    # Initialize GLM-OCR with config file
    config_path = Path(__file__).parent / "config.yaml"
    print(f"Loading config from: {config_path}")

    # Process each page
    markdown_parts: list[str] = []
    with GlmOcr(config_path=str(config_path)) as ocr:
        for i, image in enumerate(images, 1):
            print(f"Processing page {i}/{len(images)}...")
            try:
                md_content = image_to_markdown(ocr, image)
                markdown_parts.append(md_content)
            except Exception as e:
                print(f"Warning: Failed to process page {i}: {e}", file=sys.stderr)
                continue

    # Write output (no page separators per spec)
    final_content = "\n\n".join(markdown_parts)
    output_path.write_text(final_content, encoding="utf-8")
    print(f"Output saved to: {output_path}")


def process_single_pdf(pdf_path: Path, output_dir: Path) -> bool:
    """Process a single PDF file. Returns True on success."""
    output_path = output_dir / (pdf_path.stem + ".md")
    try:
        convert_pdf_to_markdown(pdf_path, output_path)
        return True
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert PDF to Markdown using GLM-OCR"
    )
    parser.add_argument("input", type=Path, help="Input PDF file or folder containing PDFs")
    parser.add_argument(
        "-o", "--output", type=str, default=None, help="Output filename (only for single file)"
    )
    parser.add_argument(
        "-d", "--dir", type=str, default="./output", help="Output directory"
    )

    args = parser.parse_args()
    output_dir = Path(args.dir)
    input_path = args.input

    if input_path.is_dir():
        # Process all PDFs in the folder
        pdf_files = sorted(input_path.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in: {input_path}", file=sys.stderr)
            sys.exit(1)

        print(f"Found {len(pdf_files)} PDF files in {input_path}")
        success_count = 0
        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
            if process_single_pdf(pdf_file, output_dir):
                success_count += 1

        print(f"\nCompleted: {success_count}/{len(pdf_files)} files processed successfully")

    elif input_path.is_file():
        # Process single PDF file
        if args.output:
            output_path = output_dir / args.output
        else:
            output_path = output_dir / (input_path.stem + ".md")
        convert_pdf_to_markdown(input_path, output_path)

    else:
        print(f"Error: Input not found: {input_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

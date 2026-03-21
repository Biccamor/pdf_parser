from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

def parse(sciezka_do_pdf):
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_table_structure = False 
    
    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )    
    wynik = doc_converter.convert(sciezka_do_pdf)
    
    return wynik.document.export_to_markdown()

print(parse("pdfs/pdf1.pdf"))
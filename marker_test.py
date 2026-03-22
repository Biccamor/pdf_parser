from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
import magic

def parser(file):

    converter = PdfConverter(
        artifact_dict=create_model_dict(),  
    )
    rendered = converter(file)
    text, _, images = text_from_rendered(rendered)

    return text


#parser("pdfs/pdf1.pdf")


if __name__ == "__main__":
    parser("pdfs/pdf1.pdf")

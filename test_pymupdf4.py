import pymupdf4llm

path = "pdfs/4.pdf"
md = pymupdf4llm.to_markdown(path)
print(md)


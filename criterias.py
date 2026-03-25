import re
import unicodedata

def delete_others_unicode(text):
    "".join(chr for chr in text if unicodedata.category(chr)[0] != "C" or chr in "\n\t") # check if character is weird char
    return text

def images(text):
    picture_tags = text.count("picture [") # check if there are too many images compared to text if so then it is badly foramted
    words = len(text.split())
    
    if words > 0 and (picture_tags / words) > 0.02: 
        return True
    return False

def years(text) -> bool:
    if re.search(r"\d{4}\s+\d{4}", text): # check if dates arent spammed if they are then it is badly formated
        return True
    return False
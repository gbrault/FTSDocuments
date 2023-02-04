import os
from bs4 import BeautifulSoup as bs
import cssutils

def pdf2htmlEX(pdf_path, html_path=os.path.join("fts-data","EX")):
    os.system(os.path.join("pdf2htmlEX")+os.sep+'pdf2htmlEX.exe --zoom 1.3 --dest-dir %s %s' % (html_path, pdf_path))

def html2txt(html_path, txt_path=os.path.join("fts-data","EX")):
    if ".html" not in html_path:
        html_path1 = html_path+".html"
        txt_path1 = html_path+".txt"
    else:
        html_path1 = html_path
        txt_path1 = html_path.replace(".html",".txt")
    with open(os.path.join(txt_path,html_path1), 'r', encoding="utf-8") as f:
        soup = bs(f, 'html.parser')
        selectortextrules  = {}
        for styles in soup.find_all('style'):
            new_rules = {}
            for rule in cssutils.parseString(styles.encode_contents().decode()):
                if hasattr(rule, 'selectorText'):
                    new_rules.update({ rule.selectorText : {style.name: style.value for style in rule.style} })
            selectortextrules.update(new_rules)
        # to access style
        # selectortextrules['.x1']['left']
        with open(os.path.join(txt_path,txt_path1), 'w', encoding="utf-8") as f:
            for div in soup.find('body').find('div',{"id": "page-container"}).find_all('div'):
                if div.has_attr('data-page-no'):
                    text = div['data-page-no']
                    page = int(f"0x{text}",0)
                    f.write(f"Page ({page})\n")
                elif div['class'][0] == 't':
                    spans = div.find_all('span')
                    if len(spans) > 0:
                        for span in spans:
                            text = "["+span.get_text()+"]"
                            if text != "":
                                f.write(text)
                    else:
                        f.write(div.get_text())
                    f.write("\n")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    # -s: pdf source path
    parser.add_argument('-p', "--source", help='source path')
    # -d: html path
    parser.add_argument('-d', "--html", help='html path')
    # -f: full processing = pdf2htmlEX + html2txt
    parser.add_argument('-f', "--full", help='full processing')

    args = parser.parse_args()
    # if -s is not None, then convert pdf to html
    if args.source is not None:
        pdf2htmlEX(args.source)
    # if -h is not None, then convert html to txt
    if args.html is not None:
        html2txt(args.html)
    # if -f is not None, then convert pdf to html and html to txt
    if args.full is not None:
        pdf2htmlEX(args.full+".pdf")
        html_path = os.path.basename(args.full).replace(".pdf","")
        html2txt(html_path)

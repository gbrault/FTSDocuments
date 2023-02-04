import os
from bs4 import BeautifulSoup as bs
import cssutils

def pdf2htmlEX(pdf_path, html_path=os.path.join("fts-data","EX")):
    os.system(os.path.join("pdf2htmlEX")+os.sep+'pdf2htmlEX.exe --zoom 1.3 --dest-dir %s %s' % (html_path, pdf_path))

def cluster_by_page_and_vertical_overlap(blocs):
    # blocs = [{"page":1, "left":1, "bottom":1, "height":1, "line":"line1", "font_size":1}, {"page":1, "left":1, "bottom":2, "height":2, "line":"line2", "font_size":2}, ...]
    # clusters are such that: blocs in a cluster are on the same page and vertically overlap with the cluster rectangle
    # the cluster rectangle is the smallest rectangle that contains all blocs in the cluster
    # the cluster rectangle is defined by its bottom, top, left and right coordinates

    # create a dictionnary of blocks by page
    pages = {}
    for bloc in blocs:
        if bloc['page'] not in pages:
            pages[bloc['page']] = []
        pages[bloc['page']].append(bloc)
    # cluster blocks by page
    clusters = {}
    for page in pages:
        # sort blocs by bottom, left
        page_blocs = sorted(pages[page], key=lambda k: (-k['bottom'], k['left']))
        # find all blocs that overlap with the bloc at the top of the stack
        pitch = -2
        while True:
            if len(page_blocs) == 0:
                break
            top_bloc = page_blocs.pop(0)
            if pitch == -1:
                # calculate pitch which is the difference between top_bloc and the bloc at the top of the previous bloc added to the cluster
                pitch = clusters[page][-1]['blocs'][-1]['bottom'] - top_bloc['bottom']
                last_pitch = pitch
            elif pitch != -2:
                last_pitch = pitch
                pitch = top_bloc['bottom'] - clusters[page][-1]['blocs'][-1]['bottom']

            if len(clusters) == 0 or page not in clusters:
                clusters[page] =[{"blocs":[top_bloc], "bottom":top_bloc['bottom'], "top":top_bloc['bottom']+top_bloc['height'], "left":top_bloc['left'], "right":top_bloc['left']+len(top_bloc['line'])*top_bloc['font_size']/2}]
                pitch = -1
            else:
                # I need to find if there is a cluster that overlaps with the top_bloc
                # if yes, I need to add the top_bloc to the cluster
                # if no, I need to create a new cluster
                found = False
                for cluster in clusters[page]:
                    # top_bloc vertical overlap with cluster
                    if top_bloc['bottom'] < cluster['top'] and top_bloc['bottom']+top_bloc['height'] > cluster['bottom'] and ( # vertical overlap
                       # same font size
                          ( top_bloc['font_size'] == cluster['blocs'][0]['font_size'] ) 
                    ):
                        if last_pitch !=-1 and last_pitch != pitch:
                            # if pitch changed, this is a candidate for a new cluster
                            break
                        cluster['blocs'].append(top_bloc)
                        cluster['bottom'] = min(cluster['bottom'], top_bloc['bottom'])
                        cluster['top'] = max(cluster['top'], top_bloc['bottom']+top_bloc['height'])
                        cluster['left'] = min(cluster['left'], top_bloc['left'])
                        cluster['right'] = max(cluster['right'], top_bloc['left']+len(top_bloc['line'])*top_bloc['font_size']/2)
                        found = True
                        break
                if not found:
                    # need to create a new cluster
                    clusters[page].append({"blocs":[top_bloc], "bottom":top_bloc['bottom'], "top":top_bloc['bottom']+top_bloc['height'], "left":top_bloc['left'], "right":top_bloc['left']+len(top_bloc['line'])*top_bloc['font_size']/2})
    return clusters

def html2txt(html_path, txt_path=os.path.join("fts-data","EX"), begin_sep = "",end_sep =""): # begin_sep="[") #, end_sep = "]"):
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
        blocs = []
        for div in soup.find('body').find('div',{"id": "page-container"}).find_all('div'):
            if div.has_attr('data-page-no'):
                text = div['data-page-no']
                page = int(f"0x{text}",0)
            elif div['class'][0] == 't':
                left = float(selectortextrules['.'+div['class'][2]]['left'][:-2])
                height = float(selectortextrules['.'+div['class'][3]]['height'][:-2])
                bottom = float(selectortextrules['.'+div['class'][4]]['bottom'][:-2])
                font_familly = selectortextrules['.'+div['class'][5]]['font-family']
                font_size = float(selectortextrules['.'+div['class'][6]]['font-size'][:-2])
                font_color = selectortextrules['.'+div['class'][7]]['color']
                spans = div.find_all('span')
                if len(spans) > 0:
                    line = ""
                    for item in div.contents:
                        if item.name == 'span':
                            line += begin_sep+item.text+end_sep 
                        else:
                            line += begin_sep+item+end_sep
                else:
                    line = begin_sep+div.get_text()+end_sep
                bloc = {"page":page, "left":left, "height":height, "bottom":bottom, "font_familly":font_familly, "font_size":font_size, "font_color":font_color, "line":line}
                blocs.append(bloc)
        # cluster blocks
        clusters = cluster_by_page_and_vertical_overlap(blocs)

    with open(os.path.join(txt_path,txt_path1), 'w', encoding="utf-8") as f:
        for page in sorted(clusters.keys()):
            f.write(f"Page {page}\n")
            i = 0
            for cluster in clusters[page]:
                f.write(f"  Cluster {i}\n")
                i += 1
                latsx = -1
                for bloc in sorted(cluster['blocs'], key=lambda k: (k['left'],-k['bottom'])):
                    if bloc['left'] != latsx and latsx != -1:
                        f.write(f"\n    =====\n")
                        latsx = bloc['left']
                    else:
                        latsx = bloc['left']
                    f.write(f"    {bloc['page']}-{i} - {round(bloc['left'],2)} - {round(bloc['bottom'],2)} {round(bloc['height'],2)} - {bloc['font_familly']} - {bloc['font_size']} - {bloc['font_color']} - {bloc['line']}\n")

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

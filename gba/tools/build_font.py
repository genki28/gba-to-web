"""Build a reproducible 16px monochrome JIS font; no private notes as inputs."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'fonts/NotoSansCJKjp-Regular.otf'
font=ImageFont.truetype(str(source),16)
codes=[]
for n in range(0x20,0x10000):
 if 0x7f<=n<0xa0:continue
 try: chr(n).encode('iso2022_jp')
 except UnicodeEncodeError:continue
 codes.append(n)
rows=[]
for n in codes:
 im=Image.new('L',(16,16));ImageDraw.Draw(im).text((0,14),chr(n),font=font,fill=255,anchor='ls')
 rows.append([sum((1<<(15-x)) for x in range(16) if im.getpixel((x,y))>=96) for y in range(16)])
header='/* Generated Cue Bitmap JP, derived from Noto Sans CJK JP. OFL: fonts/OFL.txt. */\n'
header+=f'#define JP_GLYPH_COUNT {len(codes)}\n'
header+='static const uint16_t jp_codes[]={'+','.join(map(str,codes))+'};\n'
header+='static const uint16_t jp_rows[][16]={\n'+',\n'.join('{'+','.join(hex(r) for r in rs)+'}' for rs in rows)+'\n};\n'
(ROOT/'font_jp.h').write_text(header)
(ROOT.parent/'dist/hardware/font-coverage.js').write_text('// Generated from the public JIS font, never from private notes.\nexport const SUPPORTED_CODEPOINTS=new Set('+json.dumps(codes)+');\n')
(ROOT/'fonts/manifest.json').write_text(json.dumps({'font':'Cue Bitmap JP 16 (derived bitmap)','source':'Noto Sans CJK JP Regular','url':'https://github.com/notofonts/noto-cjk/tree/main/Sans','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'license':'SIL Open Font License 1.1','glyphs':len(codes),'pixels':16,'threshold':96,'baseline':14},indent=2))
print('glyphs',len(codes),'ROM font bytes',len(codes)*34)
